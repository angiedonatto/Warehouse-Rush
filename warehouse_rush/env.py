"""Grid environment: reach the end point from the start point around random obstacles.

Coordinates are (x, y) with x growing right and y growing up; (0, 0) is bottom-left.
"""
from collections import deque

import gymnasium as gym
import numpy as np
from gymnasium import spaces

ACTION_NAMES = ["UP", "DOWN", "LEFT", "RIGHT"]
MOVES = [(0, 1), (0, -1), (-1, 0), (1, 0)]

STEP_REWARD = -1.0
BUMP_REWARD = -5.0
GOAL_REWARD = 20.0


class GridEnv(gym.Env):
    metadata = {"render_modes": ["ansi"]}

    def __init__(self, size=8, n_obstacles=10, max_steps=None, render_mode=None):
        if n_obstacles > size * size - 2:
            raise ValueError("too many obstacles for the grid")
        self.size = size
        self.n_obstacles = n_obstacles
        self.max_steps = max_steps or 4 * size * size
        self.render_mode = render_mode
        self.start = (0, 0)
        self.goal = (size - 1, size - 1)
        self.action_space = spaces.Discrete(4)
        # x, y, blocked flag (obstacle or wall) and visited-this-episode flag for
        # each of UP, DOWN, LEFT, RIGHT
        self.observation_space = spaces.MultiDiscrete([size, size] + [2] * 8)
        self.obstacles = frozenset()
        self.pos = self.start
        self.steps = 0
        self.visited = set()
        self.optimal_length = None

    # -- layout -------------------------------------------------------------
    def _blocked(self, cell):
        x, y = cell
        return not (0 <= x < self.size and 0 <= y < self.size) or cell in self.obstacles

    def shortest_path_length(self):
        """BFS length from start to goal, or None if unreachable."""
        queue, seen = deque([(self.start, 0)]), {self.start}
        while queue:
            cell, dist = queue.popleft()
            if cell == self.goal:
                return dist
            for dx, dy in MOVES:
                nxt = (cell[0] + dx, cell[1] + dy)
                if nxt not in seen and not self._blocked(nxt):
                    seen.add(nxt)
                    queue.append((nxt, dist + 1))
        return None

    def _sample_obstacles(self):
        free = [
            (x, y)
            for x in range(self.size)
            for y in range(self.size)
            if (x, y) not in (self.start, self.goal)
        ]
        while True:  # resample until a path exists
            idx = self.np_random.choice(len(free), self.n_obstacles, replace=False)
            self.obstacles = frozenset(free[i] for i in idx)
            self.optimal_length = self.shortest_path_length()
            if self.optimal_length is not None:
                return

    # -- gym API ------------------------------------------------------------
    def _obs(self):
        x, y = self.pos
        flags = [int(self._blocked((x + dx, y + dy))) for dx, dy in MOVES]
        seen = [int((x + dx, y + dy) in self.visited) for dx, dy in MOVES]
        return np.array([x, y, *flags, *seen], dtype=np.int64)

    def _info(self):
        return {
            "pos": self.pos,
            "obstacles": sorted(self.obstacles),
            "optimal_length": self.optimal_length,
        }

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self._sample_obstacles()
        self.pos = self.start
        self.steps = 0
        self.visited = {self.start}
        return self._obs(), self._info()

    def step(self, action):
        self.steps += 1
        dx, dy = MOVES[int(action)]
        nxt = (self.pos[0] + dx, self.pos[1] + dy)
        if self._blocked(nxt):
            reward, event = BUMP_REWARD, "bump"
        else:
            self.pos, reward, event = nxt, STEP_REWARD, "move"
            self.visited.add(nxt)
        terminated = self.pos == self.goal
        if terminated:
            reward, event = GOAL_REWARD, "goal"
        truncated = not terminated and self.steps >= self.max_steps
        info = self._info()
        info["event"] = event
        return self._obs(), reward, terminated, truncated, info

    def render(self):
        rows = []
        for y in reversed(range(self.size)):
            row = []
            for x in range(self.size):
                c = (x, y)
                row.append(
                    "A" if c == self.pos else "S" if c == self.start
                    else "G" if c == self.goal else "#" if c in self.obstacles else "."
                )
            rows.append(f"{y} " + " ".join(row))
        rows.append("  " + " ".join(str(x) for x in range(self.size)))
        return "\n".join(rows)
