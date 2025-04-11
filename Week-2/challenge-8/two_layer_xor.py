import numpy as np

# Sigmoid activation function and its derivative
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sigmoid_derivative(x):
    return x * (1 - x)

# XOR input and output
X = np.array([
    [0, 0],
    [0, 1],
    [1, 0],
    [1, 1]
])
y = np.array([[0], [1], [1], [0]])

# Initialize weights and biases
np.random.seed(42)
W1 = np.random.randn(2, 2)   # weights: input → hidden
b1 = np.random.randn(1, 2)   # bias for hidden layer
W2 = np.random.randn(2, 1)   # weights: hidden → output
b2 = np.random.randn(1, 1)   # bias for output

# Hyperparameters
learning_rate = 0.1
epochs = 10000

# Training loop
for epoch in range(epochs):
    # Forward pass
    z1 = np.dot(X, W1) + b1
    a1 = sigmoid(z1)
    z2 = np.dot(a1, W2) + b2
    a2 = sigmoid(z2)

    # Backpropagation
    delta2 = (a2 - y) * sigmoid_derivative(a2)
    dW2 = np.dot(a1.T, delta2)
    db2 = np.sum(delta2, axis=0, keepdims=True)

    delta1 = np.dot(delta2, W2.T) * sigmoid_derivative(a1)
    dW1 = np.dot(X.T, delta1)
    db1 = np.sum(delta1, axis=0, keepdims=True)

    # Update weights and biases
    W2 -= learning_rate * dW2
    b2 -= learning_rate * db2
    W1 -= learning_rate * dW1
    b1 -= learning_rate * db1

# Test the trained network
print("\nXOR Gate Predictions:")
for i in range(4):
    x = X[i]
    z1 = np.dot(x, W1) + b1
    a1 = sigmoid(z1)
    z2 = np.dot(a1, W2) + b2
    a2 = sigmoid(z2)
    output = 1 if a2[0][0] >= 0.5 else 0
    print(f"Input: {x.tolist()}, Output: {output} (Raw: {a2[0][0]:.4f})")
