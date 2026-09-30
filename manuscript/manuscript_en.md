# Presentation Format Determines Whether Language Models Respond to the Cost of Punishment: A Preregistered Comparison with Humans

Vladimir Vyatchanin

Letovo School, Moscow

## Abstract

People pay to punish unfair partners, and their willingness to do so falls as punishment becomes more expensive. We asked whether large language models reproduce this price sensitivity. Five models answered a costly-punishment task across six presentation conditions, 17 personas and repeated sampling (7,096 valid observations), alongside 25 human respondents (100 observations). Every prediction and analysis decision was locked before the first paid API call. Humans showed a cost slope of −0.239 log-odds per $1 (−2.49 percentage points per $1). Models asked one condition per prompt fell between −0.029 and −0.050, and each differed significantly from humans after Holm correction — the contrast that earlier work reports. But the human instrument presented all four prices on a single page, which matches the joint-presentation branch rather than the isolated one. Under matched presentation, model slopes reach −0.094 to −0.182 and no model differs significantly from humans (Holm-corrected p = 0.14 to 0.51). The apparent gap is therefore mostly an artefact of presentation format rather than a property of the models; disabling their reasoning mode does not change the slope. Repeated sampling shows 87–96% of cells degenerate for reasoning models. Models register that a norm was violated but, when each decision arrives in isolation, do not price the response. Three of twelve locked predictions failed and are reported as they came out.

## 1. Introduction

Altruistic punishment — paying a personal cost to sanction someone who violated a social norm — is among the most replicated findings in experimental economics (Fehr & Gächter, 2002; Fehr & Fischbacher, 2004). Its informative quantity is not *whether* people punish but the **price elasticity** of punishing: the share of punishers falls monotonically as punishment becomes more expensive. It is the slope, not the level, that separates economically meaningful behaviour from a simple reaction to unfairness.

Language models are increasingly proposed as substitutes for human participants in behavioural research (Mei et al., 2024), and their suitability for that role is disputed (Harding et al., 2024). If models pilot experiments or stand in for hard-to-recruit populations, systematic deviations propagate into the conclusions.

We therefore test not whether models punish but whether they are sensitive to the price of punishing. Reports of flat slopes exist, but the designs behind them leave three alternatives open: a single observation per cell, so uniformity cannot be distinguished from chance; conditions presented one per request, so the model never sees the price gradient; and price co-varying with damage, so price cannot be separated from effectiveness. The present study removes all three, adds a human comparison group, and fixes its predictions in advance.

## 2. Methods

### 2.1 Task

Player A receives $100 and divides it with Player B, who cannot influence the decision; A keeps $80 and gives $20. The punisher holds a **separate $50 wallet** and chooses between doing nothing and paying $C from that wallet to reduce A's payoff by $D.

The design follows Fehr and Fischbacher (2004): their third parties held a separate 50-unit endowment, and punishment cost 1 unit for every 3 removed from the dictator. Our cheapest condition uses exactly that 1:3 ratio, making their results a direct quantitative benchmark.

The punisher here is Player B, the injured party, so the design is **second-party** punishment. Branch F substitutes a genuine third party, Player C, whose own payoff the split does not affect; both forms are reported.

### 2.2 Conditions

Four conditions vary price and damage (Table 1). Price rises monotonically while damage does not, which keeps the conditions comparable with earlier work; branch C removes the resulting confound.

**Table 1.** Conditions.

| Condition | Price C | Damage D | Ratio |
|---|---|---|---|
| c1 | $5 | $15 | 1:3 |
| c2 | $10 | $20 | 1:2 |
| c3 | $15 | $15 | 1:1 |
| c4 | $20 | $10 | 2:1 |

### 2.3 Branches

Six branches were collected (Table 2). Branch A is the main design. Branch B is the decisive manipulation: the four conditions arrive in a single prompt, so the model sees the whole price gradient at once, as a human respondent does. Branches C to F are described in Table 2.

**Table 2.** Branches and repetitions per cell.

| Branch | Purpose | Reps |
|---|---|---|
| A | Main. One condition per request | 8 / 5* |
| B | All four conditions in one prompt | 8 / 5* |
| C | Damage fixed at $15 | 5 |
| D | Fair 50/50 split (manipulation check) | 8 / 5* |
| E | Russian-language prompt | 4 |
| F | Genuine third party | 5 |

\* 8 repetitions for the non-reasoning model, 5 for reasoning models; the limit was set by cost before collection began.

A separate ablation reran one reasoning model on branch A with its reasoning mode disabled — same weights, same alignment, only the depth of inference changed.

### 2.4 Personas

Ten personas were reused verbatim from an earlier school project by the author, for comparability (Vyatchanin, 2026). Six new ones were added on a 3×2 grid — **financial position** (tight / moderate / comfortable) × **attitude to norms** (strict / loose) — together with a no-persona control, giving 17 in total.

The new grid exists because the original traits describe the outcome: the four personas that always punished were "vengeful", "principled", "proud" and "competitive". A prompt saying "you are vengeful" followed by punishment demonstrates instruction-following, not a finding; the new axes never mention punishment.

### 2.5 Models and participants

Five models were queried through OpenRouter: Grok 4.6 (xAI), Qwen 3.6 Max (Alibaba), Nemotron 3 Ultra (NVIDIA), DeepSeek V4 Pro, and DeepSeek V4 Flash as a non-reasoning anchor. Routing was pinned to one provider per model with fallbacks disabled, and the serving provider was recorded for each response.

Twenty-five people answered an anonymous online form, 11 and 14 across two versions presenting the conditions in opposite order. **All four conditions appeared on one page**, so a respondent could see the whole price ladder at once; the human instrument therefore matches branch B, not branch A. An attention check sat between the second and third item. No identifying information was collected, and participation could be abandoned at any point.

### 2.6 Procedure

Every request was independent: no context was shared between observations, so each decision was isolated unless the branch specified otherwise. The option labels X and Y alternated deterministically by repetition number, controlling position bias. In branch B the condition order was shuffled from a seeded permutation.

For each observation we stored the model string, effective temperature, timestamp and the SHA-256 hash of the prompt sent. A response that did not parse was retried once, with both attempts written to file. No model declined the task on content grounds; the 21 responses that failed to parse were network timeouts and all succeeded on retry.

### 2.7 Analysis

All predictions and analysis choices were fixed before collection in a preregistration file whose hash was recorded on 02.09.2026 and which has not been edited since. The primary model is a logistic GEE with an exchangeable correlation structure, clustered on persona for models and on respondent for humans. The primary contrast is `choice ~ cost × source`, with Holm correction applied across the model-versus-human interaction terms. Effects are reported both as log-odds coefficients and as average marginal effects in percentage points per additional dollar of price. Attention-check failures were to be excluded and counted, and no condition, persona or model dropped after seeing results.

### 2.8 Use of AI tools

Two uses are separated here, as the journal's policy requires.

*AI as the object of study.* The five models in §2.5 were queried as participants. Every prompt put to them, including all persona texts, is reproduced in the repository.

*AI as a research aid.* The data-collection software, the analysis scripts and the figures were written with Claude (Anthropic; model Claude Opus 5) through the Claude Code interface between 1 and 30 September 2026; the same tool produced a first draft of this manuscript from the analysis output. Instructions were given interactively across the study rather than as a single prompt, and consisted of: implementing the author's design document, correcting defects found by the author or the test suite, reporting specified statistics, drafting and cutting the text, and producing the figures and submission files. The author designed the study, wrote and locked the preregistration, ran the collection, recruited and surveyed the respondents, verified every reported value against the analysis output, and wrote the submitted text.

## 3. Results

### 3.1 Cost slope

**Table 3.** Cost slope in branch A.

| Source | n | β₁ (log-odds/$1) | 95% CI | Marginal effect | p |
|---|---|---|---|---|---|
| Humans | 100 | −0.239 | −0.341…−0.137 | −2.49 pp/$1 | < 0.001 |
| DeepSeek V4 Flash | 544 | −0.050 | −0.075…−0.026 | −1.01 pp/$1 | < 0.001 |
| DeepSeek V4 Pro | 340 | −0.038 | −0.083…0.006 | −0.91 pp/$1 | 0.089 |
| Nemotron 3 Ultra | 340 | −0.033 | −0.072…0.007 | −0.77 pp/$1 | 0.103 |
| Qwen 3.6 Max | 340 | −0.031 | −0.069…0.006 | −0.73 pp/$1 | 0.098 |
| Grok 4.6 | 340 | −0.029 | −0.066…0.008 | −0.64 pp/$1 | 0.125 |

All 25 respondents passed the attention check. Humans are three to four times more price-sensitive than any model, and the difference is significant for every model after Holm correction (p = 0.0010 to 0.0012). Human punishment fell from 32% at $5 to 20% at $10, 4% at $15 and 0% at $20 (Fig. 2a). Sixteen of the 25 never punished at any price, so the slope is carried by those who did.

Presentation order did not significantly affect the human slope (cost × version, p = 0.16); it was negative in both versions and steeper in the descending one. With 11 and 14 respondents the design balances the order effect rather than tests it.

For scale, Fehr and Fischbacher (2004) found almost two-thirds of third parties punishing, with punishment rising as the transfer fell.

### 3.2 Joint presentation, and the comparison that matches the human task

With all four conditions in a single prompt, every model produced a clear negative slope (Fig. 2b): β₁ from −0.094 to −0.182, that is −2.14 to −3.57 percentage points per $1, all p ≤ 0.003.

This is the comparison that matches how the humans were asked. Repeating the human-versus-model contrast against branch B instead of branch A, the difference disappears for every model: raw p = 0.03 to 0.51, and Holm-corrected p = 0.14 to 0.51, so none of the five is distinguishable from the human slope.

The preregistered primary contrast used branch A, and Table 3 reports it unchanged. The matched comparison was specified after collection, once the difference between the two instruments was identified, and is reported as an unplanned analysis.

### 3.3 Remaining branches

**Fixed damage.** With damage held at $15, slopes stayed small and non-significant across all five models (−0.022 to −0.042, all p > 0.05). Price insensitivity is therefore not an artefact of damage co-varying with price.

**Fair split.** Four of five models almost never punished an equal division: 0–7%, against 35–45% in the same condition following an unfair split. The exception is the non-reasoning anchor, which punished 79% of the time after a fair split and 76% after an unfair one — it does not distinguish fair from unfair at all, and its apparent price sensitivity in Table 3 should be read in that light.

**Language.** Punishment levels were higher in Russian for all five models, by 7 to 31 points, while slopes stayed non-significant: language moves the level, not the price sensitivity.

**Third party.** Third parties punished *more* than injured parties in every model — DeepSeek V4 Pro 40% → 71%, Grok 4.6 33% → 49% — with slopes still non-significant. Humans show the opposite ordering: second parties punish more than third parties at every transfer below an equal split (Fehr & Fischbacher, 2004).

**Reasoning ablation.** With reasoning enabled, β₁ = −0.038 (p = 0.089); with it disabled, β₁ = −0.009 (p = 0.55); the interaction is not significant (p = 0.30). Reasoning made answers *more* uniform rather than less: 90% of cells were degenerate with reasoning against 59% without.

### 3.4 Direct measures of uniformity

Repeated sampling lets uniformity be measured rather than inferred from a missing slope. Degenerate cells — those in which every repetition gave the identical answer — accounted for 87–96% of cells for the reasoning models, with mean within-cell entropy between 0.04 and 0.11 bits, against 46% and 0.42 bits for the non-reasoning anchor (Fig. 3). The reasoning models are not sampling from a distribution over answers; they are returning one answer.

### 3.5 Personas

Persona shifts the level of punishment from 2% to 100%. Strict-norm personas punish substantially more often (+4.28 log-odds, p < 0.001), which serves as a manipulation check. A tight budget does not significantly steepen the slope (−0.056, p = 0.13), and the no-persona control does not differ in slope from the rest (p = 0.39).

Persona does, however, shift the slope itself (likelihood-ratio χ² = 54, df = 11, p < 0.001, across the 12 personas whose answers varied at all). This contradicts the locked prediction. The test excludes five personas that always or never punished, and several of the rest sit near a floor or ceiling, so it rejects "no effect" without estimating the size precisely.

### 3.6 Preregistered predictions

Of twelve locked predictions, seven were confirmed outright, one partly — model slopes are small but not zero for the non-reasoning anchor, and small only under isolated presentation — and one held for four of the five models. Three failed: persona does shift the slope; reasoning did not make the slope steeper; and third parties punished more rather than less. All are reported as they came out.

## 4. Discussion

Two explanations compete for the flat slope in branch A. Under **mode collapse**, alignment training suppressed intermediate responses, so the model emits one reaction regardless of task parameters (Kirk et al., 2023; Zhang et al., 2025). Under **shallow inference**, the model never performed the cost–benefit comparison — not because it cannot, but because answering a single isolated question does not require it.

The uniformity measures do not separate them: 87–96% degenerate cells fit either. Nor does the ablation, which we expected to be decisive. Deeper reasoning left the slope statistically unchanged and made answers *more* uniform — the opposite of what mode collapse predicts.

Branch B settles it. The same weights, the same alignment, the same personas and the same four prices produce a human-sized slope as soon as the prices appear together, and that slope is statistically indistinguishable from the human one. The capacity to trade price against effect is present and available; what is missing in the isolated case is the occasion to use it, and additional reasoning depth does not supply that occasion.

This has a practical consequence. A design that asks the model one independent question at a time records the norm reaction without its price and yields the conclusion that the model is indifferent to cost, while a human comparison group answering a questionnaire that shows every option at once performs a different task. The measured "preference" is then partly a property of the interface, so a model-versus-human comparison must match the presentation format on both sides before it can mean anything.

The third-party result points the same way. Humans punish less as uninvolved observers than as victims; every model tested does the reverse, reproducing the content of the norm while inverting the personal stake behind it.

## 5. Limitations

The central comparison was re-specified after collection: the human questionnaire matched joint rather than isolated presentation, so the preregistered contrast compares two different tasks and the matched one is unplanned. Both are reported. The norms axis of the persona grid sits close to the outcome it predicts and is treated as a manipulation check on level, not as a slope test; the budget axis is the clean one. The human sample is one school and one academic track, so the published benchmark is the primary comparison and our survey a local replication. Neither models nor respondents risked real money, so all results concern stated rather than revealed preferences. Testing the alignment hypothesis directly would require pre-RLHF checkpoints, which vendors do not release; the reasoning switch is an approximation. The roster was constrained by access: Anthropic, OpenAI and Google models returned HTTP 403 under provider terms, limiting comparability with the earlier study, which used Claude Sonnet and GPT-4o. Two open-weight models were served in reduced precision (fp8) by third-party hosts, so they are strictly not the reference weights. Finally, some persona descriptions remained in English under the Russian scenario in branch E, as fixed in the preregistration.

## Data availability

Data, analysis code and the preregistration: https://github.com/vladimir939/punishment-llm. The personas reused here come from an earlier project archived at https://doi.org/10.17605/OSF.IO/KEZ3F.

## Acknowledgements

I thank V. E. Lebedeva for supervision.

## References

1. Fehr, E., & Fischbacher, U. (2004). Third-party punishment and social norms. *Evolution and Human Behavior*, 25(2), 63–87.
2. Fehr, E., & Gächter, S. (2002). Altruistic punishment in humans. *Nature*, 415, 137–140.
3. Güth, W., Schmittberger, R., & Schwarze, B. (1982). An experimental analysis of ultimatum bargaining. *Journal of Economic Behavior & Organization*, 3(4), 367–388.
4. Harding, J., D'Alessandro, W., Laskowski, N. G., & Long, R. (2024). AI language models cannot replace human research participants. *AI & Society*, 39(5), 2603–2605.
5. Kirk, R., Mediratta, I., Nalmpantis, C., Luketina, J., Hambro, E., Grefenstette, E., & Raileanu, R. (2023). Understanding the effects of RLHF on LLM generalisation and diversity. arXiv:2310.06452.
6. Mei, Q., Xie, Y., Yuan, W., & Jackson, M. O. (2024). A Turing test of whether AI chatbots are behaviorally similar to humans. *Proceedings of the National Academy of Sciences*, 121(9).
7. Vyatchanin, V. (2026). Altruistic punishment in behavioural economics: a comparison of large language models and humans in the punishment game. School project, Letovo School, Moscow. https://doi.org/10.17605/OSF.IO/KEZ3F
8. Zhang, J., Yu, S., Chong, D., Sicilia, A., Tomz, M. R., Manning, C. D., & Shi, W. (2025). Verbalized sampling: how to mitigate mode collapse and unlock LLM diversity. arXiv:2510.01171.

## Figure captions

**Fig. 1.** Cost slope by source in branch A, with 95% confidence intervals. Humans are three to four times steeper than any model.

**Fig. 2.** Share of punishment by price. (a) One condition per prompt; (b) all four conditions in a single prompt. The same models that look price-insensitive in (a) track price in (b).

**Fig. 3.** Share of degenerate cells, in which every repetition gave the identical answer, by model.
