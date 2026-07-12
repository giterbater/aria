# Memory Influence Investigation Results

## Experiment Design

- **Seeds per condition**: 200
- **Episodes per seed**: 100
- **Total episodes**: 160,000 (8 conditions × 200 seeds × 100 episodes)
- **All combinations tested**: Memory, Identity, Values, and their pairings

---

## Results Table

| Condition | Mean | 95% CI | Δ vs Baseline | Cohen's d | p-value | Significant? |
|-----------|------|--------|---------------|-----------|---------|--------------|
| Baseline | 0.6043 | [0.5974, 0.6112] | — | — | — | — |
| Memory Only | 0.6916 | [0.6848, 0.6985] | **+14.5%** | 1.773 | <0.001 | Yes*** |
| Identity Only | 0.6236 | [0.6168, 0.6303] | +3.2% | 0.392 | <0.001 | Yes*** |
| Values Only | 0.6007 | [0.5939, 0.6074] | -0.6% | -0.074 | 0.457 | No |
| Memory + Identity | 0.6862 | [0.6790, 0.6934] | +13.6% | 1.620 | <0.001 | Yes*** |
| Memory + Values | 0.6895 | [0.6824, 0.6965] | +14.1% | 1.692 | <0.001 | Yes*** |
| Identity + Values | 0.6179 | [0.6109, 0.6248] | +2.2% | 0.272 | 0.006 | Yes** |
| Full System | 0.6869 | [0.6799, 0.6939] | +13.7% | 1.656 | <0.001 | Yes*** |

---

## Key Findings

### 1. Memory Influence is the Dominant Mechanism

Memory Only achieves **+14.5%** improvement with a large effect size (d=1.773). This is the single biggest contributor.

### 2. Identity Adds a Small but Significant Effect

Identity Only achieves **+3.2%** improvement (d=0.392, p<0.001). This is statistically significant but practically small.

### 3. Values Alone Don't Help

Values Only shows **-0.6%** (not significant). Values require memory to be useful.

### 4. Subadditive Interactions

When combined with memory, identity and values actually **reduce** performance slightly:

| Combination | Additive Prediction | Actual | Interaction |
|-------------|---------------------|--------|-------------|
| Memory + Identity | 0.711 | 0.686 | **-0.025** |
| Memory + Values | 0.688 | 0.690 | +0.001 |
| Full System | 0.707 | 0.687 | **-0.020** |

The negative interaction suggests identity and values create slight interference with memory's optimization.

---

## Why Memory Influence Works

### Mechanism

1. **Success at 'inform' (80% base rate)** → positive influence signal
2. **Failure at 'warn' (30% base rate)** → negative influence signal
3. **Agent learns to prefer 'inform' and avoid 'warn'**
4. **Probability concentrates on high-success actions**

### Observed Preference Shifts

| Action | Base Rate | Memory-Only Rate | Shift |
|--------|-----------|------------------|-------|
| inform | 0.250 | 0.419 | **+0.169** |
| execute | 0.250 | 0.234 | -0.016 |
| query | 0.250 | 0.271 | +0.021 |
| warn | 0.250 | 0.075 | **-0.175** |

The agent learns to:
- **Double** its selection of 'inform' (0.25 → 0.42)
- **Reduce** 'warn' by 70% (0.25 → 0.08)

### Theoretical Analysis

- **Baseline (uniform)**: 0.25×0.8 + 0.25×0.6 + 0.25×0.7 + 0.25×0.3 = **0.60**
- **Optimal (always pick 'inform')**: **0.80**
- **Memory-only achieved**: **0.69**
- **Gap to optimal**: 0.11

The memory system captures about 75% of the possible improvement (0.09 / 0.12 = 75%).

### Correlation

Preference shift correlates with success rate: **r = 0.163** (weak but positive)

Agents that shift their preferences more tend to perform slightly better.

---

## Interpretation

### Memory Influence is Essentially Reinforcement Learning

The memory influence mechanism acts like a simple RL signal:
- Successful actions get reinforced (positive influence)
- Failed actions get penalized (negative influence)
- Agent concentrates probability on successful actions

This is not surprising—it's a well-known mechanism. What's interesting is that it works well in this simple form.

### Identity and Values Are Supporting Mechanisms

Identity and values don't directly improve performance. They:
- Create behavioral consistency (identity)
- Detect value conflicts (values)
- May provide robustness under stress (not tested here)

But they don't add to memory's performance improvement—they actually slightly interfere.

### The Full System is Memory-Dominated

The Full System (+13.7%) performs slightly worse than Memory Only (+14.5%). This suggests:
- Memory is doing the heavy lifting
- Identity and values add overhead without proportional benefit
- The system could be simplified to memory-only for pure performance

---

## Recommendations

1. **For maximum performance**: Use Memory Only
2. **For behavioral consistency**: Add Identity
3. **For stress resilience**: Add Values (requires further testing)
4. **For research**: Study why identity/values interfere with memory optimization

---

## Statistical Notes

- **CI for baseline**: [0.5974, 0.6112] (for the baseline mean)
- **CI for difference**: Calculated separately for each comparison
- **p-values**: From Welch's t-test (unequal variances)
- **Effect sizes**: Cohen's d with pooled standard deviation

---

*Generated: 2026-07-05*
*Experiment: 200 seeds × 8 conditions × 100 episodes = 160,000 episodes*
