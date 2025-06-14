import pandas as pd
import numpy as np
import os
from datetime import datetime

def compare_recommendations(golden_csv, coprocessor_csv, tolerance=0.5, mismatch_threshold_percent=5.0):
    """
    Compare two recommendation CSV files. The result is a simple PASS or FAIL.
    On PASS, a summary CSV is created. On FAIL, detailed error CSVs are created.
    """
    
    # Initial setup printout
    print("=== Recommendation CSV Verification ===")
    print(f"Golden: {golden_csv}")
    print(f"Coprocessor: {coprocessor_csv}")

    try:
        df_golden = pd.read_csv(golden_csv)
        df_coprocessor = pd.read_csv(coprocessor_csv)
    except FileNotFoundError as e:
        print(f"ERROR: File not found - {e}")
        return False
    except Exception as e:
        print(f"ERROR reading files: {e}")
        return False

    # Perform the merge to analyze differences
    id_cols = ['user_id', 'item_id']
    merged_df = pd.merge(
        df_golden, df_coprocessor, on=id_cols, how='outer', 
        indicator=True, suffixes=('_golden', '_coprocessor')
    )

    # --- Calculate ID Mismatches ---
    uncommon_rows = merged_df[merged_df['_merge'] != 'both']
    id_mismatch_count = len(uncommon_rows)
    total_unique_pairs = len(merged_df)
    id_mismatch_percent = (id_mismatch_count / total_unique_pairs) * 100 if total_unique_pairs > 0 else 0
    
    # --- Calculate Rating Mismatches (on common rows only) ---
    common_rows = merged_df[merged_df['_merge'] == 'both'].copy()
    common_rows_count = len(common_rows)
    rating_mismatch_count = 0
    rating_mismatch_percent = 0.0
    if common_rows_count > 0:
        rating_diff = abs(common_rows['predicted_rating_golden'] - common_rows['predicted_rating_coprocessor'])
        rating_mismatch_count = (rating_diff > tolerance).sum()
        rating_mismatch_percent = (rating_mismatch_count / common_rows_count) * 100

    # --- Determine Final Pass/Fail Status ---
    passed_id_check = id_mismatch_percent <= mismatch_threshold_percent
    passed_rating_check = rating_mismatch_percent <= mismatch_threshold_percent
    passed = passed_id_check and passed_rating_check

    if passed:
        # --- SUCCESS CASE: New Message and Summary CSV ---
        print("🎉 VERIFICATION PASSED!")
        print("   The coprocessor results align with the golden model specifications.")
        
        # Create a summary report DataFrame
        summary_data = {
            'status': ['PASSED'],
            'verification_timestamp': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            'golden_file': [os.path.abspath(golden_csv)],
            'coprocessor_file': [os.path.abspath(coprocessor_csv)],
            'common_pairs_verified': [common_rows_count],
        }
        summary_df = pd.DataFrame(summary_data)
        
        # Write the summary to a CSV file
        output_file = "verification_summary.csv"
        try:
            summary_df.to_csv(output_file, index=False)
            print(f"   A summary report has been saved to: {os.path.abspath(output_file)}")
        except Exception as e:
            print(f"   Warning: Could not write summary file. {e}")

    else:
        # --- FAILURE CASE: Detailed Output ---
        print("❌ VERIFICATION FAILED!")
        
        # Print the detailed analysis only on failure
        print("\n--- Failure Analysis ---")
        print(f"Total unique (user, item) pairs across both files: {total_unique_pairs}")
        print(f"ID Mismatches (pairs in one file): {id_mismatch_count} ({id_mismatch_percent:.2f}%)")
        print(f"\nCommon pairs found in both files: {common_rows_count}")
        print(f"Rating Mismatches (on common pairs): {rating_mismatch_count} ({rating_mismatch_percent:.2f}%)")
        print("-" * 25)

        if not passed_id_check:
            print(f"Reason: ID Mismatch rate ({id_mismatch_percent:.2f}%) exceeded threshold ({mismatch_threshold_percent}%)")
            mismatch_details = uncommon_rows[id_cols + ['_merge']].copy()
            mismatch_details['_merge'] = mismatch_details['_merge'].replace({'left_only': 'in_golden_only', 'right_only': 'in_coprocessor_only'})
            mismatch_details.rename(columns={'_merge': 'source_file'}, inplace=True)
            output_file = "id_mismatches.csv"
            mismatch_details.to_csv(output_file, index=False)
            print(f"Details saved to: {os.path.abspath(output_file)}\n")

        if not passed_rating_check:
            print(f"Reason: Rating Mismatch rate ({rating_mismatch_percent:.2f}%) exceeded threshold ({mismatch_threshold_percent}%)")
            mismatched_ratings = common_rows[abs(common_rows['predicted_rating_golden'] - common_rows['predicted_rating_coprocessor']) > tolerance].copy()
            mismatched_ratings['difference'] = abs(mismatched_ratings['predicted_rating_golden'] - mismatched_ratings['predicted_rating_coprocessor'])
            output_df = mismatched_ratings[['user_id', 'item_id', 'predicted_rating_golden', 'predicted_rating_coprocessor', 'difference']]
            output_file = "rating_mismatches.csv"
            output_df.to_csv(output_file, index=False)
            print(f"Details saved to: {os.path.abspath(output_file)}\n")
            
    return passed

def main():
    GOLDEN_CSV = os.path.join('..', '..', '01_python_software_only', 'COB_advanced', 'recommendations.csv')
    COPROCESSOR_CSV = os.path.join('..', 'recommendations.csv')
    
    print(f"Running script from: {os.getcwd()}")

    passed = compare_recommendations(
        GOLDEN_CSV, 
        COPROCESSOR_CSV, 
        tolerance=0.5, 
        mismatch_threshold_percent=5.0
    )
    
    print("-" * 40)
    if passed:
        print("Final Status: PASSED")
    else:
        print("Final Status: FAILED")

if __name__ == "__main__":
    main()