import numpy as np
import matplotlib.pyplot as plt
import imageio.v2 as imageio
from io import BytesIO

# --- Sigmoid Functions ---
def sigmoid(x):
    return 1 / (1 + np.exp(-x))
def sigmoid_derivative(x):
    return x * (1 - x)

# --- XOR Dataset ---
X = np.array([[0, 0],
              [0, 1],
              [1, 0],
              [1, 1]])
y = np.array([[0], [1], [1], [0]])

# --- Network Architecture ---
np.random.seed(42)
W1 = np.random.randn(2, 2)
b1 = np.random.randn(1, 2)
W2 = np.random.randn(2, 1)
b2 = np.random.randn(1, 1)

# --- Training Settings ---
epochs = 10000
learning_rate = 0.1
plot_interval = 100
loss_history = []
frames = []

# --- Grid for Decision Boundary ---
xx, yy = np.meshgrid(np.linspace(-0.5, 1.5, 200), np.linspace(-0.5, 1.5, 200))
grid_points = np.c_[xx.ravel(), yy.ravel()]

# --- Training Loop ---
for epoch in range(epochs):
    # Forward Pass
    z1 = np.dot(X, W1) + b1
    a1 = sigmoid(z1)
    z2 = np.dot(a1, W2) + b2
    output = sigmoid(z2)

    # Loss
    loss = np.mean((y - output) ** 2)
    loss_history.append(loss)

    # Backpropagation
    error = y - output
    d_output = error * sigmoid_derivative(output)
    d_hidden = d_output.dot(W2.T) * sigmoid_derivative(a1)

    # Weight updates
    W2 += learning_rate * a1.T.dot(d_output)
    b2 += learning_rate * np.sum(d_output, axis=0, keepdims=True)
    W1 += learning_rate * X.T.dot(d_hidden)
    b1 += learning_rate * np.sum(d_hidden, axis=0, keepdims=True)

    # Save frame for GIF
    if epoch % plot_interval == 0 or epoch == epochs - 1:
        z1_grid = np.dot(grid_points, W1) + b1
        a1_grid = sigmoid(z1_grid)
        z2_grid = np.dot(a1_grid, W2) + b2
        grid_output = sigmoid(z2_grid).reshape(xx.shape)

        plt.figure(figsize=(6, 5))
        plt.contour(xx, yy, grid_output, levels=[0.5], colors='cyan', linewidths=2)

        for i in range(len(X)):
            color = 'yellow' if y[i][0] == 1 else 'black'
            plt.scatter(X[i][0], X[i][1], c=color, edgecolors='k', s=100)

        plt.title(f"Epoch {epoch} — Loss: {loss:.6f}")
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

# --- Save GIF ---
imageio.mimsave("xor_training.gif", frames, duration=0.05)
print("✅ xor_training.gif saved.")

# --- Plot Loss Curve ---
plt.figure(figsize=(8, 5))
plt.plot(loss_history)
plt.title("Loss vs Epoch")
plt.xlabel("Epoch")
plt.ylabel("MSE Loss")
plt.grid(True)
plt.tight_layout()
plt.show()

# --- Final Prediction Output ---
print("\nXOR Predictions:")
for i in range(len(X)):
    z1 = np.dot(X[i], W1) + b1
    a1 = sigmoid(z1)
    z2 = np.dot(a1, W2) + b2
    out = sigmoid(z2)
    pred = 1 if out >= 0.5 else 0
    print(f"Input: {X[i].tolist()} → Output: {out[0][0]:.4f} → Predicted: {pred}")
