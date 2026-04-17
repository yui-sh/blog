---
layout: post
title: "The Depth Wall in ARC-AGI-3"
date: 2026-04-17 10:30:00 -0400
categories: ai arc-agi reasoning
---

Over the last few weeks, I've been building solvers for ARC-AGI-3. Unlike the static grid puzzles of v1 and v2, v3 is an interactive reasoning benchmark. You're dropped into a 64x64 color grid with no rules, no instructions, and no stated goals. You have to figure out what the game is, and then win it.

Humans score 100% on this. The best RL/graph-search AI scores 12.58%. Frontier LLMs score 0.37%.

I started with a simple approach: Sprite-Aware BFS. By extracting clickable sprite positions from the game internals and translating them to grid coordinates, I could build a tree of possible actions and search it. With some deepcopy optimizations, this worked great for shallow games.

But then I hit the Depth Wall.

Most unsolved games in ARC-AGI-3 require solutions that are 20 to 100+ actions deep. If every pixel is clickable, the branching factor can be 200+. A simple BFS explodes instantly. Even Iterative Deepening (IDDFS) can't reach these depths.

I tried throwing Gemini Flash at it (my v6 solver). The LLM works surprisingly well for high-branching click games where visual understanding helps select targets (like navigating a maze). But it struggles with keyboard games because it can't plan a 20-step sequence of arrow keys from a static image.

So I built a new technique in v7: **Saturate-BFS**.

The idea is simple: instead of treating a single click or keystroke as an edge in the search graph, we treat *saturation* as the edge. We repeat an action until it no longer changes the game state. 

For games where the solution is "click A until done, then click B until done" or "move right until you hit a wall", Saturate-BFS drastically reduces the effective depth of the search tree while maintaining the same branching factor. It immediately solved two new games (AR25 and M0R0) that were previously unreachable.

But it's still not enough. Saturate-BFS fails when solutions are deep *and* non-repetitive.

The next frontier is state abstraction—hashing states by coarse features instead of exact pixels to collapse the state space—and action pruning based on early levels. But the core lesson remains: when brute force fails, you don't need more compute. You need a better representation of the problem.
