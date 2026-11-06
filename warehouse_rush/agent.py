import numpy as np


class QAgent:
    """Tabular Q-learning over (x, y, blocked + visited flags of the 4 neighbours)."""

    def __init__(self, size, alpha=0.2, gamma=0.97, seed=0):
        self.q = np.zeros((size, size, *[2] * 8, 4))
        self.alpha, self.gamma = alpha, gamma
        self.rng = np.random.default_rng(seed)

    def act(self, obs, epsilon=0.0):
        if self.rng.random() < epsilon:
            return int(self.rng.integers(4))
        values = self.q[tuple(obs)]
        return int(self.rng.choice(np.flatnonzero(values == values.max())))

    def update(self, obs, action, reward, next_obs, terminated):
        target = reward + (0 if terminated else self.gamma * self.q[tuple(next_obs)].max())
        self.q[(*obs, action)] += self.alpha * (target - self.q[(*obs, action)])

    def save(self, path):
        np.save(path, self.q)

    def load(self, path):
        self.q = np.load(path)
