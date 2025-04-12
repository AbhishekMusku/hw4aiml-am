import numpy as np
import matplotlib.pyplot as plt

# Sigmoid functions
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def sigmoid_derivative(x):
    return x * (1 - x)

# XOR data
X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
y = np.array([[0], [1], [1], [0]])

# Initialize parameters
np.random.seed(42)
weights = np.random.randn(2, 1)
bias = np.random.randn(1)

# Training config
learning_rate = 0.1
epochs = 10000
plot_interval = 2500

# Meshgrid for decision surface
xx, yy = np.meshgrid(np.linspace(-0.5, 1.5, 200), np.linspace(-0.5, 1.5, 200))
grid_points = np.c_[xx.ravel(), yy.ravel()]

# Training loop
for epoch in range(epochs):
    z = np.dot(X, weights) + bias
    output = sigmoid(z)
    error = y - output
    adjustment = error * sigmoid_derivative(output)
    weights += learning_rate * np.dot(X.T, adjustment)
    bias += learning_rate * np.sum(adjustment)

    # Plot decision boundary at selected epochs
    if epoch % plot_interval == 0 or epoch == epochs - 1:
        z_grid = np.dot(grid_points, weights) + bias
        grid_output = sigmoid(z_grid).reshape(xx.shape)

        plt.figure(figsize=(8, 6))
        plt.contourf(xx, yy, grid_output, 50, cmap='plasma', alpha=0.9)
        plt.colorbar(label="Output")

        for i in range(len(X)):
            color = 'yellow' if y[i][0] == 1 else 'black'
            plt.scatter(X[i][0], X[i][1], c=color, edgecolors='k', marker='o', s=100)

        contour = plt.contour(xx, yy, grid_output, levels=[0.5], colors='cyan', linewidths=2, linestyles='solid')
        try:
            contour.collections[0].set_label("Decision Boundary")
        except (AttributeError, IndexError):
            pass

        plt.title(f"Decision Boundary after Epoch {epoch}")
        plt.xlabel("Input1")
        plt.ylabel("Input2")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

# Final weights and output (optional)
print("\nFinal Weights and Bias After 10,000 Epochs:")
print(f"w1: {weights[0][0]}")
print(f"w2: {weights[1][0]}")
print(f"bias: {bias[0]}")

print("\nXOR Gate Predictions:")
for i in range(4):
    z = np.dot(X[i], weights) + bias
    out = sigmoid(z)
    pred = 1 if out >= 0.5 else 0
    print(f"Input: {X[i].tolist()}, Raw Output: {out[0]:.4f}, Binary Output: {pred}")
