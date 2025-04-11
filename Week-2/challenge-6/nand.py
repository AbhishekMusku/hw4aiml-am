import numpy as np

# Sigmoid activation and its derivative
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sigmoid_derivative(x):
    return x * (1 - x)

# NAND gate training data
X = np.array([
    [0, 0],
    [0, 1],
    [1, 0],
    [1, 1]
])
y = np.array([[1], [1], [1], [0]])  # Expected output

# Initialize weights and bias
np.random.seed(42)
weights = np.random.randn(2, 1)
bias = np.random.randn(1)

# Training parameters
learning_rate = 0.1
epochs = 10000

# Training loop
for epoch in range(epochs):
    z = np.dot(X, weights) + bias
    output = sigmoid(z)
    error = y - output
    adjustment = error * sigmoid_derivative(output)
    weights += learning_rate * np.dot(X.T, adjustment)
    bias += learning_rate * np.sum(adjustment)

# Prompt user for custom input
print("\nModel trained! Now you can test it with your own input.")
try:
    a = int(input("Enter first input (0 or 1): "))
    b = int(input("Enter second input (0 or 1): "))
    if a not in [0, 1] or b not in [0, 1]:
        raise ValueError("Inputs must be 0 or 1.")

    user_input = np.array([a, b])
    z = np.dot(user_input, weights) + bias
    out = sigmoid(z)
    binary_out = 1 if out >= 0.5 else 0

    print(f"\nInput: [{a}, {b}] → Raw Output: {out[0]:.4f}, Binary Output: {binary_out}")

except ValueError as e:
    print("Invalid input:", e)
