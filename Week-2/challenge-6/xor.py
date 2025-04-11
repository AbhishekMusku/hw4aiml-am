import numpy as np
# Sigmoid activation function and its derivative
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sigmoid_derivative(x):
    return x * (1 - x)

# XOR gate truth table
X = np.array([
    [0, 0],
    [0, 1],
    [1, 0],
    [1, 1]
])
y = np.array([[0], [1], [1], [0]])

# Initialize weights and bias
np.random.seed(42)
weights = np.random.randn(2, 1)
bias = np.random.randn(1)

# Training parameters
learning_rate = 0.1
epochs = 10000
loss_history = []

# Training loop
for epoch in range(epochs):
    z = np.dot(X, weights) + bias
    output = sigmoid(z)
    error = y - output
    loss = np.mean(error ** 2)
    loss_history.append(loss)

    adjustment = error * sigmoid_derivative(output)
    weights += learning_rate * np.dot(X.T, adjustment)
    bias += learning_rate * np.sum(adjustment)

# Final weights and bias
print("\nFinal Weights and Bias After 10,000 Epochs:")
print(f"w1: {weights[0][0]}")
print(f"w2: {weights[1][0]}")
print(f"bias: {bias[0]}")

# Final output after training
print("\nXOR Gate Predictions:")
for i in range(4):
    input_pair = X[i]
    z = np.dot(input_pair, weights) + bias
    out = sigmoid(z)
    pred = 1 if out >= 0.5 else 0
    print(f"Input: {input_pair.tolist()}, Raw Output: {out[0]:.4f}, Binary Output: {pred}")



