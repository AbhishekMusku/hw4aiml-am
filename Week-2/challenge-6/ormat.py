import numpy as np
import matplotlib.pyplot as plt
import imageio.v2 as imageio
from io import BytesIO

def sigmoid(x):
    return 1 / (1 + np.exp(-x))
def sigmoid_derivative(x):
    return x * (1 - x)

X = np.array([[0, 0], [0, 1], [1, 0], [1, 1]])
y = np.array([[0], [1], [1], [1]])  # OR logic

np.random.seed(42)
weights = np.random.randn(2, 1)
bias = np.random.randn(1)

epochs = 10000
learning_rate = 0.1
plot_interval = 50
frames = []

xx, yy = np.meshgrid(np.linspace(-0.5, 1.5, 200), np.linspace(-0.5, 1.5, 200))
grid_points = np.c_[xx.ravel(), yy.ravel()]

for epoch in range(epochs):
    z = np.dot(X, weights) + bias
    output = sigmoid(z)
    error = y - output
    adjustment = error * sigmoid_derivative(output)
    weights += learning_rate * np.dot(X.T, adjustment)
    bias += learning_rate * np.sum(adjustment)

    if epoch % plot_interval == 0 or epoch == epochs - 1:
        z_grid = np.dot(grid_points, weights) + bias
        grid_output = sigmoid(z_grid).reshape(xx.shape)

        plt.figure(figsize=(6, 5))
        plt.contourf(xx, yy, grid_output, 50, cmap='plasma', alpha=0.9)
        plt.colorbar(label="Output")

        for i in range(len(X)):
            color = 'yellow' if y[i][0] == 1 else 'black'
            plt.scatter(X[i][0], X[i][1], c=color, edgecolors='k', s=100)

        plt.contour(xx, yy, grid_output, levels=[0.5], colors='cyan')
        plt.title(f"OR - Epoch {epoch}")
        plt.xlabel("Input 1")
        plt.ylabel("Input 2")
        plt.grid(True)
        plt.tight_layout()

        buf = BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        frames.append(imageio.imread(buf))
        buf.close()

imageio.mimsave("or_training.gif", frames, duration=0.05)
print("✅ GIF saved as or_training.gif")
