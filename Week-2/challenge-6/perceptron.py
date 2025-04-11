import numpy as np

# Sigmoid activation function
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

# Simple perceptron (1 neuron, 2 inputs)
class Perceptron:
    def __init__(self):
        # Random weights for 2 inputs
        self.weights = np.random.randn(2)
        self.bias = np.random.randn(1)

    def forward(self, x):
        z = np.dot(x, self.weights) + self.bias
        output = sigmoid(z)
        return output

# Example usage
if __name__ == "__main__":
    print("Enter two binary inputs (0 or 1):")
    try:
        x1 = int(input("Input 1: "))
        x2 = int(input("Input 2: "))
        if x1 not in [0, 1] or x2 not in [0, 1]:
            raise ValueError("Inputs must be 0 or 1.")
    except ValueError as e:
        print("Invalid input:", e)
        exit()

    inputs = np.array([x1, x2])
    model = Perceptron()
    output = model.forward(inputs)
    print("Raw Output (sigmoid):", output)
    binary_output = 1 if output >= 0.5 else 0
    print("Binary Output (0 or 1):", binary_output)
