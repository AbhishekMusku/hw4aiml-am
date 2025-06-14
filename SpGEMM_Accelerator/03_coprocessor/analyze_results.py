import re
import os
import pandas as pd # Import the pandas library

def parse_verilog_time(logfile="sim.log"):
    """
    Parses the simulation log to find the LAST hardware execution time listed.
    """
    time_pattern = re.compile(r"Execution time:\s+([\d\.]+) seconds")
    hw_time_sec = None
    try:
        with open(logfile, "r") as f:
            for line in f:
                match = time_pattern.search(line)
                if match:
                    # Always overwrite with the latest match found
                    hw_time_sec = float(match.group(1))
    except FileNotFoundError:
        return None # Return None if log file not found
    return hw_time_sec

def get_time_from_csv(filename, column_name):
    """
    Reads a single value from the first row of a CSV file.
    """
    try:
        df = pd.read_csv(filename)
        if not df.empty and column_name in df.columns:
            return df.iloc[0][column_name]
    except FileNotFoundError:
        return None # Return None if CSV not found
    except KeyError:
        return None # Return None if column not found
    return None

def save_summary_to_csv(summary_data, filename="final_pipeline_summary.csv"):
    """
    Saves the final summary dictionary to a CSV file.
    """
    try:
        df = pd.DataFrame([summary_data])
        df.to_csv(filename, index=False)
        print(f"\nFinal summary successfully saved to {filename}")
    except Exception as e:
        print(f"\nError saving final summary to CSV: {e}")

def main():
    """
    Main function to analyze the results after simulation.
    """
    print("\n" + "="*60)
    print("ANALYZING SIMULATION RESULTS")
    print("="*60)

    # --- 1. Get Hardware Performance ---
    hardware_time_sec = parse_verilog_time()
    
    if hardware_time_sec is None or hardware_time_sec <= 0:
        print("ERROR: Could not find a valid hardware execution time in sim.log.")
        print("Please ensure you have run 'make | tee sim.log' successfully.")
        return

    # --- 2. Get Data Transfer Info ---
    try:
        with open("in.csv", "r") as f:
            total_frames = sum(1 for line in f) - 1
            if total_frames <= 0:
                print("ERROR: in.csv is empty or not found.")
                return
    except FileNotFoundError:
        print("ERROR: in.csv not found. Please run the simulation first.")
        return

    # --- 3. Calculate and Print Hardware Metrics ---
    total_bytes = total_frames * 9
    total_bits = total_bytes * 8
    throughput_kbps = (total_bits / hardware_time_sec) / 1000.0
    
    print("--- Hardware Accelerator Performance ---")
    print(f"  - Total Frames Processed: {total_frames}")
    print(f"  - Total Bytes Transferred: {total_bytes}")
    print(f"  - Hardware Execution Time: {hardware_time_sec:.9f} seconds")
    print(f"  - Calculated Throughput:   {throughput_kbps:.2f} kbps")
    
    # --- 4. Get Software Timings from CSV files ---
    cob1_time = get_time_from_csv("cob1_timing_stats.csv", "phase1_time_sec")
    
    cob3_cf_time = get_time_from_csv("performance_stats.csv", "collaborative_filtering_time_sec")
    cob3_rec_time = get_time_from_csv("performance_stats.csv", "top_recommendations_time_sec")
    
    cob3_time = None
    if cob3_cf_time is not None and cob3_rec_time is not None:
        cob3_time = cob3_cf_time + cob3_rec_time

    # --- 5. Print the Final End-to-End Summary ---
    print("\n" + "="*60)
    print("ESTIMATED 'REAL-LIFE' END-TO-END PIPELINE TIME")
    print("="*60)

    # Dictionary to hold all final results for saving
    final_summary_data = {
        'total_frames_processed': total_frames,
        'total_bytes_transferred': total_bytes,
        'hw_execution_time_sec': hardware_time_sec,
        'hw_throughput_kbps': throughput_kbps
    }

    if cob1_time is not None and cob3_time is not None:
        total_pipeline_time = cob1_time + hardware_time_sec + cob3_time
        print(f"  - SW Pre-processing (cob1):      {cob1_time:.4f} seconds")
        print(f"  - Physical HW Execution (est.):  {hardware_time_sec:.4f} seconds")
        print(f"  - SW Post-processing (cob3):     {cob3_time:.4f} seconds")
        print("  -------------------------------------------------")
        print(f"  ESTIMATED TOTAL PIPELINE TIME:   {total_pipeline_time:.4f} seconds")

        # Add software and total times to the summary data
        final_summary_data['sw_preprocessing_sec'] = cob1_time
        final_summary_data['sw_postprocessing_sec'] = cob3_time
        final_summary_data['total_pipeline_time_sec'] = total_pipeline_time
    else:
        print("  Could not calculate total pipeline time.")
        if cob1_time is None:
            print("  - Reason: 'cob1_timing_stats.csv' not found or is invalid.")
        if cob3_time is None:
            print("  - Reason: 'performance_stats.csv' not found or is invalid.")
            
    print("="*60)

    # --- 6. Save the final summary to a new CSV file ---
    save_summary_to_csv(final_summary_data)


if __name__ == "__main__":
    main()
