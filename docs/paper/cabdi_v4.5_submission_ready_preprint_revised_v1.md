
---
title: "CABDI: Constrained Cognitive Routing under Measurement Uncertainty"
subtitle: "A physiology-free theorem layer with optional biobehavioral sensing"
author: "Vitalii Krumin"
bibliography: cabdi_bibliography_v6.bib
link-citations: true
---

## Abstract

Human-AI systems often fail not because model predictions are weak, but because assistance is delivered at the wrong time, in the wrong form, or under the wrong verification regime. We formulate this problem as constrained partially observable control over assistance mode, verification depth, interaction friction, and compute allocation under measurement uncertainty. CABDI is presented here as a behavior-first structured subclass of constrained partially observable routing problems in which human-AI collaboration is modeled as a dual-rate closed loop with latent operator state, integrity risk, task mode, and operator-specific response parameters, observed through behavioral telemetry, task evidence, signal-quality diagnostics, and optional physiological channels.

The strongest contribution of the paper is not a physiology-aware controller as such, but a formal admissibility boundary separating behaviorally supportable routing claims from physiology-dependent incremental-value claims. The theorem layer is therefore intentionally physiology-free. Physiology, when present, is treated only as an optional, artifact-prone auxiliary channel that may refine state estimation but cannot enlarge the admissible claim space by itself. CABDI introduces explicit operator-response dynamics, a behavior-first witness estimator, tier-scoped adaptation that prevents cross-tier calibration leakage, and an identified reduced slow routing model family for the scalar-safe theorem case. The reduced surrogate is no longer left as an unspecified empirical placeholder: the paper now constrains it to admitted reduced-model families fitted on tier-consistent logs and accepted only after holdout prediction, local-gain certification, and envelope-diagnostic checks.

The main-text theory consists of a supporting practical-stability proposition for this scalar-safe controller over an admissible bounded-sensitivity operator-response class, a structural theorem showing that optimal assistance policies are generically non-monotone once overload and catastrophic-risk structure are modeled explicitly, and an observation-map sufficiency proposition that blocks latent-state overclaiming under partial observability. The appendices strengthen the proof layer specifically where it carries the most weight: the non-monotone regime theorem and the claim-admissibility result. The paper also adds a stylized synthetic sanity check showing how the regime logic can be instantiated in a behavior-first simulator without physiological channels. This synthetic exercise is not empirical validation; it is a coherence check on the control logic.

This preprint establishes a constrained-control framework, an admissibility discipline, and a falsification protocol. It should be rejected or sharply narrowed if behavior-only adaptive routing already saturates observable gains, if physiology adds no incremental value under matched compute and risk, if the reduced slow surrogate fails admission or runtime envelope checks, or if the scalar-safe controller cannot sustain practical control even in stylized synthetic settings. The framework is therefore strongest not where it measures more, but where it claims less while retaining routing value.

## 1. Introduction

Human–AI systems are increasingly deployed in settings where failure is not merely a matter of lower convenience or reduced throughput, but of consequential error. Even when the underlying model is strong, system-level failure often arises from a different source: not from insufficient raw prediction quality, but from interaction mismatch. Advice may arrive too early or too late, in a form that is too terse or too expansive, with too little verification burden, or under assumptions about the human operator’s state that are simply false. In this sense, many practical failures of human–AI systems are not failures of intelligence alone; they are failures of routing [@vaccaro2024meta; @gonzalez2026science].

Two recurring pathologies illustrate the problem. The first is **overreliance**: operators accept model outputs despite contradictory evidence, insufficient justification, or the model’s lower relative competence. The second is **underutilization**: helpful assistance is ignored or abandoned because the interaction arrives at the wrong moment, imposes the wrong cognitive burden, or fails to match the task regime. These pathologies are usually studied separately, but they share a common structure. Both emerge when the system treats the human operator as a static receiver rather than as a time-varying, partially observed decision process whose monitoring capacity, strain level, reliance calibration, and tolerance for interaction evolve during the task. CABDI begins from a simple claim: state-blind interaction is a design flaw [@gao2021bandit; @gonzalez2025cognitive].

Existing system design often addresses the problem only locally. One line of work improves model calibration or uncertainty reporting. Another studies interface cues, interruption control, or decision support. A third focuses on test-time compute, search, or verification depth. These are all useful, but they are typically optimized in isolation. What is missing is a unified formalism in which assistance mode, compute allocation, verification depth, interaction friction, and safety constraints are treated as coupled control variables inside a single partially observable system. CABDI proposes such a formalism. It frames human–AI collaboration as a constrained routing problem over latent operator state, behavioral evidence, task context, signal-quality diagnostics, and optional physiological channels. The object of optimization is therefore not the answer in isolation, but the policy that governs how answers are produced, timed, structured, checked, and delivered.

The strongest contribution of the present paper is the **admissibility boundary**. CABDI is most useful not when it claims privileged access to hidden cognition, but when it constrains itself to routing and oversight claims that factor through observable anchors. This is why the theorem-facing layer is behavior-first and physiology-free. Optional physiological channels may improve estimation, but only as incremental-value branches over strongest non-physiology baselines. They do not justify stronger semantic claims by themselves. The historical project label “CABDI” is retained, but the central theorem layer of this version does not depend on physiology.

A second key change in this version is operational rather than rhetorical. Earlier drafts left the scalar-safe slow surrogate
\[
d_{k+1}^\star = F_d(d_k^\star,\bar a_k,\bar e_k)+\omega_k^d
\]
underdescribed. In the present paper, the reduced slow routing model \(F_d\) is constrained to an admitted identification family together with explicit acceptance checks: tier-consistent fitting, holdout one-step and multi-step prediction, empirical local-gain certification, and runtime envelope diagnostics. This does not turn CABDI into a fully identified human model. It does make the stability proposition conditional on a more concrete and auditable model class rather than on an unspecified empirical placeholder.

The paper makes five contributions. First, it defines a single formal control problem for human–AI routing under partial observability and resource constraints, explicitly positioning CABDI as a structured subclass of constrained POMDP-style problems rather than as a replacement for that literature. Second, it introduces a behavior-first witness estimator and an explicit admissible family for the reduced slow routing surrogate used by the scalar-safe theorem layer. Third, it states a supporting practical-stability proposition for the scalar-safe controller over an admissible bounded-sensitivity operator-response class and a structural theorem showing that optimal assistance policies are generically non-monotone once overload and catastrophic-risk structure are modeled explicitly. Fourth, it formalizes compute contracts and observation-map sufficiency so that routing and oversight claims remain behaviorally testable even when latent semantics are not. Fifth, it gives a staged falsification protocol together with a stylized synthetic sanity check that exercises the routing logic without pretending to be real-world validation.

The paper should be rejected or sharply narrowed under three kinds of failure. It fails first if behavior-only adaptive routing already saturates observable gains relative to strongest matched-budget baselines. It fails second if physiology adds no incremental routing value once compute, verification, and risk are controlled. It fails third if the scalar-safe surrogate cannot support practical control because the admitted reduced model family does not pass holdout, local-gain, or runtime envelope checks. These are not peripheral caveats. They are the empirical and operational conditions under which CABDI ceases to earn its stronger claims.

The rest of the paper is organized as follows. Section 2 situates the framework relative to constrained POMDPs, belief-state approximation, system identification, adaptive assistance, oversight, compute governance, and biobehavioral monitoring. Section 3 introduces the formal problem and the behavior-first witness estimator, including the admitted reduced-model family for the scalar-safe theorem case. Section 4 describes the routing architecture in deliberately compact form. Section 5 states the main theoretical results. Section 6 formalizes identifiability and claim admissibility. Section 7 gives a falsification-first evaluation protocol with a minimal first-validation path and a stylized synthetic sanity check. Sections 8 and 9 discuss implications, limitations, and conclusions.

## 2. Related Work

### 2.1 CABDI as a structured subclass of constrained partially observable control

Classical constrained MDP and constrained POMDP work provides the optimization backbone for acting under partial observability with bounded secondary costs or risks [@altman1999cmdp; @poupart2015alp; @khonji2023durative]. More recent work on recursively constrained POMDPs sharpens an additional point that is directly relevant for CABDI: when constraints are history-dependent, naive replanning can break Bellman-style consistency unless the constraint structure is made explicit [@ho2024rcpomdp]. CABDI inherits that lesson directly. It does not optimize a generic latent-state control problem. It optimizes a human-loop routing object over assistance mode, compute allocation, verification depth, and friction, with oversight and integrity constraints that are native to human–AI interaction rather than incidental technical side costs.

The point is therefore not that CABDI replaces constrained POMDP theory. It does not. CABDI narrows and structures it. RC-POMDPs explain why history-dependent burden constraints matter; CABDI specifies what those constraints are in this domain: interruption counts, verification fatigue, fallback frequency, matched-budget governance, and operator-response safety.

### 2.2 Belief approximation, decision quality, and reduced routing surrogates

Point-based solvers, value-directed belief compression, and related approximation methods were developed because exact belief evolution is generally intractable in large partially observable systems [@shani2013pointbased; @spaan2005perseus; @pineau2003pbvi; @poupart2000valuedirected]. Their core lesson is that a useful approximation is one that preserves decision quality, not one that recovers every latent semantic perfectly. CABDI agrees with that lesson, but adds a second requirement: claim discipline. A routing surrogate should not merely be useful; it should also be prevented from silently inflating into a semantic theory of cognition.

This is where reduced-model identification enters. In the scalar-safe theorem case, CABDI now constrains the reduced slow routing model \(F_d\) to explicit identified families rather than leaving it as an unspecified empirical object. That choice is compatible with contemporary system-identification practice, where ARX/NARX-style models, piecewise-affine surrogates, and neural state-space surrogates are all viable reduced models when they are fitted and benchmarked explicitly [@stefanoiu2024narmax; @dong2025arxnn]. CABDI differs from generic system identification in one decisive way: it does not seek a globally faithful operator model. It seeks a reduced surrogate whose class, acceptance tests, and local-gain certificate are explicit enough to support bounded routing claims.

### 2.3 Trust-aware planning, adaptive assistance, JITAI, and learning-to-defer

Trust-POMDP and related HRI work explicitly model hidden human variables and use planning to calibrate collaboration quality over time [@chen2018planning; @herse2024trustcalibration]. These models show that hidden human variables can be placed inside principled decision loops without pretending that they are directly observed. CABDI takes that direction but changes the target. Trust-aware models typically optimize trust calibration or a compact human latent variable. CABDI optimizes a routing tuple under oversight, integrity, and compute-governance constraints. Trust-like variables therefore appear inside CABDI as substructure of reliance calibration, not as the sole object of control.

A closely related intervention tradition treats assistance timing, type, and dose as adaptive variables rather than as fixed interface choices. JITAI research formalizes the goal of delivering the right type and amount of support at the right time under rapidly changing internal and contextual state [@nahumshani2026jitai]. Learning-to-defer and adherence-aware advice frameworks similarly study when a model should act, advise, or stay silent. CABDI is aligned with that literature but adds two things it does not usually foreground: explicit compute and verification contracts, and a theorem-facing admissibility boundary. CABDI therefore differs from generic adaptive intervention work not by rejecting it, but by embedding it inside a constrained partially observable routing problem with stronger epistemic limits.

### 2.4 Oversight, complementarity, and appropriate reliance

A large portion of the human–AI literature asks whether a human-plus-model team outperforms either component alone [@vaccaro2024meta; @gonzalez2025cognitive; @gonzalez2026science]. That framing is useful, but too coarse. Complementarity depends on when assistance is offered, how uncertainty is surfaced, how much bandwidth is consumed, whether verification is forced, and how disagreement is handled. CABDI therefore moves complementarity from a static comparison into a routing problem.

The same is true of oversight. Signal-detection framings make oversight measurable through sensitivity, criterion, commission errors, and recovery behavior rather than vague feelings of control [@langer2025oversight]. Appropriate reliance work similarly stresses that following a model is not good or bad in itself; the question is whether following it was warranted given competence and task structure [@nicolson2025xai]. CABDI internalizes that logic by turning oversight and integrity into routed objectives tied to adjudicable anchors.

### 2.5 Compute governance and neighboring test-time-control work

Another neighboring line studies test-time compute, bounded search, and dual-process inference. CWM-CI-style systems govern how an inference engine searches, verifies, and budgets compute. CABDI governs something different: when and under what human-loop contract that engine should spend compute, increase verification, compress its output, or remain silent. Model-allocation and search-allocation systems optimize the engine. CABDI optimizes the interaction policy that surrounds the engine.

The difference matters because matched-budget attribution is part of the claim contract. CABDI does not credit a routing gain to the framework if that gain disappears after matching compute, verification, and risk. This makes compute governance part of the scientific object, not merely an engineering afterthought.

### 2.6 Biobehavioral monitoring and the case for behavior-first design

The most delicate neighboring literature concerns physiological state monitoring. Multimodal sensing can improve discrimination among workload, fatigue, stress, and related conditions, but standardization remains weak and results are highly pipeline-dependent [@pereira2025workload; @orlando2025workers; @rivasvidal2026eeget]. Wearable EEG remains especially sensitive to artifact handling and hardware choices [@arpaia2025wearable; @bayat2026eeg]. CABDI therefore treats physiology as optional and quality-gated by design.

The behavior-first stance is not merely conservative; it is empirically motivated. Recent work in assistive-robot workload estimation reported that eye-gaze-centered signals outperformed EEG-centered alternatives for the target workload task, reinforcing the point that richer sensing is not automatically more useful for operational routing [@aygun2022assistiverobots]. CABDI therefore differs from physiology-heavy architectures in a concrete way: behavior is the primary theorem-facing observation layer, and physiology must earn its place only through incremental routing value under matched budgets.

### 2.7 Identifiability, metric structure, and claim discipline

The identifiability literature gives CABDI its sharpest epistemic ally. Recent work argues that one often cannot uniquely identify latent coordinates, but can identify stable relationships between them such as distances, angles, or volumes [@syrota2025metric]. That distinction maps naturally onto CABDI’s scalar-safe routing surrogate. The framework does not require a semantically privileged latent regime variable. It requires a routing-relevant control proxy that is stable enough to support decisions and bounded enough to keep claims honest.

This is why CABDI should be positioned neither as a neuro-interpretive theory of internal cognitive truth nor as a generic model-routing paper. Its distinctive move is to join constrained partially observable control, identified reduced surrogates, and claim-admissibility discipline inside a single routing framework.

## 3. Formal Problem Setup

We model human–AI collaboration as a constrained partially observable control system operating under measurement uncertainty. The goal is not merely to maximize the standalone quality of model outputs, but to optimize a routing policy over assistance, verification, interaction friction, and computational allocation.

### 3.1 CABDI as a structured constrained-POMDP subclass

Let discrete time be indexed by \(t \in \{1,\dots,T\}\). A CABDI instance is a tuple
\[
\mathcal{M}_{\mathrm{CABDI}} = (\mathcal{X},\mathcal{A},\mathcal{O}, f, g, \ell, \mathcal{C}, \Pi_{\mathrm{safe}}),
\]
where \(\mathcal{X}\) is latent operator–task state space, \(\mathcal{A}\) the routing action space, \(\mathcal{O}\) the observation space, \(f\) the latent dynamics, \(g\) the observation model, \(\ell\) the stage loss, \(\mathcal{C}\) a set of resource and safety constraints, and \(\Pi_{\mathrm{safe}}\) the admissible policy class. The framework is therefore a structured constrained partially observable control problem with human-specific state and observation semantics.

### 3.2 State, actions, and explicit operator-response dynamics

The latent state is
\[
x_t = (m_t,\ell_t,\rho_t,\theta_t,\tau_t),
\]
where:

- \(m_t \in \mathcal{M}\) denotes monitoring or oversight capacity;
- \(\ell_t \in \mathcal{L}\) denotes strain, instability, or fatigue-like load;
- \(\rho_t \in \mathcal{R}\) denotes reliance calibration state, including susceptibility to overreliance and under-reliance;
- \(\theta_t \in \Theta\) denotes slowly varying operator-specific response parameters;
- \(\tau_t \in \mathcal{T}\) denotes task mode or task family.

The action is
\[
a_t = (u_t,c_t,v_t,f_t),
\]
where \(u_t\) is assistance mode, \(c_t\) compute allocation, \(v_t\) verification depth, and \(f_t\) friction or bandwidth control.

Unlike earlier versions, the present paper does not hide the human side of the loop inside a bounded-sensitivity assumption alone. We write an explicit operator-response dynamics:
\[
x_{t+1} = f_{\tau_t}(x_t,a_t,e_t) + w_t,
\qquad
w_t \sim \mathcal{W}_{\tau_t},
\]
with a slow parameter drift
\[
\theta_{t+1} = \theta_t + \xi_t^\theta,
\qquad
\xi_t^\theta \sim \mathcal{N}(0,Q_\theta),
\]
and task-mode evolution
\[
\tau_{t+1} \sim P_\tau(\cdot \mid \tau_t,e_t,a_t).
\]

A useful decomposition is
\[
m_{t+1} = f_m(m_t,\ell_t,\rho_t,a_t,e_t;\theta_t) + \omega_t^m,
\]
\[
\ell_{t+1} = f_\ell(\ell_t,a_t,e_t;\theta_t) + \omega_t^\ell,
\]
\[
\rho_{t+1} = f_\rho(\rho_t,m_t,a_t,y_t;\theta_t) + \omega_t^\rho,
\]
where \(y_t\) denotes adjudicable feedback when available. This decomposition makes explicit what was previously only implicit: monitoring, strain, and reliance calibration may respond differently to the same intervention. The theory does not claim these components are the uniquely correct decomposition of human cognition. It claims only that an explicit admissible operator-response class is required if stability results are to mean more than “the controller behaves well under whatever hidden human dynamics you assume.” The equations above belong to the richer component-resolved view; Section 3.4 immediately distinguishes that view from the scalar-safe primary case used by the main theorem layer.

A practically important special case is trust calibration. In CABDI, trust is not introduced as a separately privileged theorem-facing state because its semantic status depends heavily on task and measurement design. Instead, short-horizon over-trust, under-trust, and repair dynamics are treated as admissible substructure inside the broader integrity-risk and reliance-calibration variable \(\rho_t\). When richer evidence is available, a component-resolved extension may factor \(\rho_t\) into trust, overreliance susceptibility, and repair propensity with asymmetric update dynamics. In the scalar-safe primary case, however, the framework only claims routing relevance for the reduced integrity-risk surrogate, not unique identifiability of trust as a standalone latent quantity.

### 3.3 Observations, signal quality, and physiology tiers

The controller receives
\[
o_t = (b_t,p_t,e_t,q_t),
\]
where:

- \(b_t\) is behavioral telemetry;
- \(p_t\) is an optional physiology channel;
- \(e_t\) is task or environment evidence;
- \(q_t\) is signal-quality and artifact state.

The observation model is
\[
b_t \sim g_b(\cdot \mid x_t,\tau_t), \qquad
e_t \sim g_e(\cdot \mid x_t,\tau_t),
\]
\[
p_t \sim g_p(\cdot \mid x_t,q_t,s_t),
\]
where \(s_t \in \{0,1,2\}\) indicates the sensing tier. A useful structured approximation is
\[
g(o_t\mid x_t,s_t) \approx g_b(b_t\mid x_t,\tau_t)\,g_e(e_t\mid x_t,\tau_t)\,g_q(q_t\mid x_t,s_t)\,g_p(p_t\mid x_t,q_t,s_t),
\]
which motivates blockwise filtering or point-based belief updates over routing-relevant subspaces rather than a monolithic generic belief update.

- **Tier 0:** behavior and task evidence only;
- **Tier 1:** behavior + light physiology (e.g., HRV, pupillometry);
- **Tier 2:** behavior + light physiology + richer channels (e.g., EEG/ET), if quality checks pass.

This tiering is not cosmetic. It formalizes the paper’s claim that physiology is optional and quality-dependent. The signal-quality state \(q_t\) may be discrete (good / degraded / invalid) or continuous. When \(q_t\) indicates degradation, physiology is downweighted or masked before entering the estimator. A generic artifact-aware effective physiology signal is
\[
\tilde p_t = \alpha(q_t)\,p_t + (1-\alpha(q_t))\,p_\varnothing,
\qquad \alpha(q_t)\in[0,1],
\]
where \(p_\varnothing\) denotes a null or conservative missing-sensor baseline. The estimator therefore acts on \(\tilde p_t\), not on raw \(p_t\).

### 3.4 Behavior-first witness estimator, calibration tiers, and routing surrogates

Because \(x_t\) is latent, the controller operates on a belief state \(\hat x_t\) inferred from observation history. The theorem layer must remain valid in the absence of physiology, so the base estimator is behavior-first and physiology-optional. The role of the witness layer is not to recover the true internal state of the operator, but to produce a routing-relevant surrogate that is calibrated, mask-aware, and stable enough to support bounded control.

A compact behavior-only witness layer is therefore defined before any physiology is admitted. Let the fast witness feature vector be partitioned into a strain-oriented block and an oversight-oriented block, both normalized task-conditionally and both robust to missingness. The controller first computes a fast routing proxy \(z_t^f\) from these observable features and only then aggregates it into the slow surrogate \(d_k\). This makes the behavior-only route fully specified rather than merely implicit, and it keeps Tier 0 scientifically complete on its own.

This behavior-first choice is not only methodological caution. It is also an empirically motivated architectural prior. In realistic deployment-like settings, behavioral observables often remain more stable across users, less fragile to artifact pipelines, and easier to calibrate than physiology-heavy alternatives [@aygun2022assistiverobots]. CABDI therefore treats behavior-first estimation not as a degraded mode that survives only when physiology is missing, but as the primary observation layer against which richer sensing must justify its incremental value.

A critical design decision is to avoid collapsing all observed irregularity into one scalar “bad state.” We therefore introduce two task-conditional feature blocks:

\[
\phi_t^{\mathrm{str}} =
\bigl(
\mathrm{RTCV}_t,\,
\mathrm{ErrorBurst}_t,\,
\mathrm{LatencySlip}_t,\,
\mathrm{PupilIndex}_t,\,
\mathrm{HRVIndex}_t
\bigr),
\]
\[
\phi_t^{\mathrm{ovr}} =
\bigl(
\mathrm{BlindAcceptance}_t,\,
\mathrm{RecoveryLag}_t,\,
\mathrm{VerifiedRecheckFail}_t,\,
\mathrm{CorrectiveOverrideGain}_t,\,
\mathrm{ContradictionLag}_t
\bigr),
\]
with physiology-dependent entries masked when absent. The first block targets strain or instability; the second targets oversight and reliance quality. This separation matters because raw signals such as override rate or revision depth are semantically ambiguous. A high override count can indicate either breakdown or competent disagreement; a high revision count can indicate either thrashing or careful correction. Outcome-conditioned features such as \(\mathrm{BlindAcceptance}\) or \(\mathrm{CorrectiveOverrideGain}\) reduce that ambiguity by anchoring behavior to whether the model should have been followed.

Let \(\mu_\tau^{\mathrm{str}}, D_\tau^{\mathrm{str}}\) and \(\mu_\tau^{\mathrm{ovr}}, D_\tau^{\mathrm{ovr}}\) be task-conditional calibration statistics, and let \(m_t^{\mathrm{str}},m_t^{\mathrm{ovr}}\) be feature-availability masks. Define standardized mask-aware features
\[
\bar \phi_t^{\mathrm{str}} = m_t^{\mathrm{str}} \odot (D_\tau^{\mathrm{str}})^{-1}\bigl(\phi_t^{\mathrm{str}}-\mu_\tau^{\mathrm{str}}\bigr),
\]
\[
\bar \phi_t^{\mathrm{ovr}} = m_t^{\mathrm{ovr}} \odot (D_\tau^{\mathrm{ovr}})^{-1}\bigl(\phi_t^{\mathrm{ovr}}-\mu_\tau^{\mathrm{ovr}}\bigr).
\]
The standardized scores are
\[
\tilde s_t = \frac{(w_\tau^{\mathrm{str}})^\top \bar \phi_t^{\mathrm{str}}}{\varepsilon + \|m_t^{\mathrm{str}}\odot w_\tau^{\mathrm{str}}\|_1},
\qquad
\tilde o_t = \frac{(w_\tau^{\mathrm{ovr}})^\top \bar \phi_t^{\mathrm{ovr}}}{\varepsilon + \|m_t^{\mathrm{ovr}}\odot w_\tau^{\mathrm{ovr}}\|_1},
\]
with task-conditional nonnegative or sign-constrained weights \(w_\tau^{\mathrm{str}},w_\tau^{\mathrm{ovr}}\). The sign constraints are not assumed universal. They are estimated or regularized using task-family prior knowledge and must be stress-tested under task shift.

Calibration must respect the admissibility boundary. Tier-0 estimators are calibrated exclusively on behavior-only data. Tier-1 and Tier-2 estimators may use richer multimodal calibration, but their parameters must not be imported into Tier-0 claim layers without explicit revalidation. Otherwise physiology would leak into a purportedly non-physiology theorem layer through the calibration path.

To block cross-tier calibration leakage through the slow operator parameters, we decompose
\[
\theta_t = \bigl(\theta_t^{\mathrm{core}},\theta_t^{(0)},\theta_t^{(1)},\theta_t^{(2)}\bigr),
\qquad
\vartheta_t = P_{s_t}\theta_t = \bigl(\theta_t^{\mathrm{core}},\theta_t^{(s_t)}\bigr),
\]
where \(P_{s_t}\) activates only the tier-compatible head. Tier-0 theorem-facing routing may depend only on \((\theta_t^{\mathrm{core}},\theta_t^{(0)})\), which are either estimated on Tier-0 data or explicitly revalidated after a tier change. When the system downgrades from Tier 2 or Tier 1 to Tier 0, the active parameters are reset to the last validated Tier-0 checkpoint,
\[
\vartheta_{t^+} = \bigl(\theta_{t^-}^{\mathrm{core}}, \theta_{\mathrm{chk}}^{(0)}\bigr),
\]
and richer-tier heads are frozen until re-admission. Thus physiology may improve a richer-tier controller without silently leaking into Tier-0 admissible claims through the parameter path.

The fast routing proxy is
\[
z_t^f = \sigma\!\left(\beta_s \tilde s_t + \beta_o \tilde o_t\right),
\]
with \(\sigma(\cdot)\) a sigmoid or equivalent monotone map into \([0,1]\). A slow proxy is obtained by filtered aggregation. Let
\[
\psi_k = \bigl(d_k,d_{k-1},\dots,d_{k-p+1},\bar a_k,\bar a_{k-1},\dots,\bar a_{k-q+1},\bar e_k,\bar e_{k-1},\dots,\bar e_{k-r+1}\bigr)
\]
be the slow lag vector built from the routing proxy, admitted slow actions, and slow task evidence. The behavior-first slow surrogate is
\[
d_k = (1-\lambda)d_{k-1} + \lambda \,\mathrm{Agg}\{z_t^f : t\in[(k-1)m+1,km]\},
\qquad \lambda\in(0,1].
\]

When physiology is present and signal quality is acceptable, it may refine the strain block or a latent filter update. Importantly, the theorem-facing controller need not consume raw physiological streams directly. It may consume only a local, quality-gated, privacy-minimized surrogate generated by the sensing layer:
\[
\hat x_t = \mathcal{E}(b_{1:t},e_{1:t},\tilde p_{1:t};\vartheta_t),
\]
but the admissible theorem layer never requires physiology to define the routing problem.

The decomposition \(x_t=(m_t,\ell_t,\rho_t,\theta_t,\tau_t)\) should be read as a structured latent-state parameterization rather than as a claim of full observational identifiability. In particular, strain \(\ell_t\) and reliance calibration \(\rho_t\) need not be separable from behavioral traces alone. Their partial separation becomes admissible only when adjudicable outcome feedback, intervention structure, or auxiliary observation channels are available.

CABDI therefore distinguishes two operating cases.

**Case S (scalar-safe primary case).** When component separation is not operationally warranted, the theorem layer closes on the slow effective surrogate \(d_k^{\mathrm{eff}}\) and the routed slow action tuple \(\bar a_k=(r_k,C_k,v_k^{\mathrm{glob}},m_k)\). The induced slow dynamics are written
\[
d_{k+1}^\star = F_d(d_k^\star,\bar a_k,\bar e_k) + \omega_k^d,
\]
where \(d_k^\star\) denotes the latent routing-relevant corridor deviation and \(\bar e_k\) aggregates slow task evidence. In the present version, \(F_d\) is not an unconstrained “empirical model that works.” It must belong to an admitted reduced-model family
\[
\mathfrak{F}_d = \mathfrak{F}_{\mathrm{ARX}} \cup \mathfrak{F}_{\mathrm{PWA}} \cup \mathfrak{F}_{\mathrm{NSS}},
\]
where \(\mathfrak{F}_{\mathrm{ARX}}\) denotes linear ARX-style surrogates on \(\psi_k\), \(\mathfrak{F}_{\mathrm{PWA}}\) piecewise-affine surrogates with bounded regionwise gains, and \(\mathfrak{F}_{\mathrm{NSS}}\) constrained nonlinear NARX or neural state-space surrogates with an explicit Jacobian or finite-difference gain certificate on the operating set [@stefanoiu2024narmax; @dong2025arxnn]. A candidate \(F_d\) is admitted only if, on tier-consistent logs from the target task family, it satisfies all of the following:

1. **holdout one-step prediction:** \(\mathrm{Err}_{1\text{-step}}\le \epsilon_1\);
2. **holdout rollout prediction:** \(\mathrm{Err}_{H\text{-step}}\le \epsilon_H\) on fixed-horizon slow windows;
3. **local-gain certificate:** empirical finite-difference gains on the operating region satisfy \(\hat L_d\le L_d^{\max}\) and \(\hat L_{\bar a}\le L_{\bar a}^{\max}\);
4. **runtime envelope compatibility:** residual inflation and calibration-drift statistics remain below pre-registered thresholds on the admission split.

The scalar-safe case is the primary theorem case of the paper. Its stability claim is therefore a **model-class result** about admitted members of \(\mathfrak{F}_d\), not a hidden claim that the full component dynamics have already been uniquely resolved.

**Case C (component-resolved extension).** When adjudicable outcome feedback, intervention structure, and tier-valid calibration make partial separation operationally available, the richer component dynamics above may be used and projected into routing through a Lipschitz map \(d_k^\star=P_c(x_k)\). Component-resolved claims are therefore an extension of the scalar-safe theorem layer, not a prerequisite for it.

### 3.5 Confidence-gated effective surrogate

The controller does not act directly on \(d_k\), but on a confidence-gated effective surrogate
\[
d_k^{\mathrm{eff}} = \kappa_k d_k + (1-\kappa_k)d_{\mathrm{safe}},
\qquad \kappa_k\in[0,1],
\]
where \(d_{\mathrm{safe}}\) is a conservative safety prior and \(\kappa_k\) is an estimator-confidence variable derived from posterior uncertainty, calibration diagnostics, and signal quality. This construction is what allows the framework to incorporate physiology without becoming physiology-dependent in the theorem layer.

### 3.6 Objective function and observation map

The routing policy is evaluated through a constrained cumulative loss:
\[
J^\pi =
\mathbb{E}_\pi\sum_{t=1}^T
\Big[
\ell_{\mathrm{task}}(x_t,a_t)
+ \lambda_1 \ell_{\mathrm{ovr}}(x_t,a_t)
+ \lambda_2 \ell_{\mathrm{intg}}(x_t,a_t)
+ \lambda_3 \ell_{\mathrm{int}}(x_t,a_t)
+ \lambda_4 \ell_{\mathrm{gov}}(x_t,a_t)
\Big].
\]

The policy is constrained by
\[
\mathbb{P}_\pi(\mathrm{CatErr}) \le \delta,\qquad
C(\pi)\le \bar C,\qquad
\pi \in \Pi_{\mathrm{safe}}.
\]

The loss terms are abstract control quantities, but they are linked to measurable anchors through an observation map
\[
\mathcal{M}(x_t,a_t,o_t,y_t) =
\bigl(
U_t,\,
d'_t,\,
\mathrm{CommErr}_t,\,
\mathrm{RecLag}_t,\,
\mathrm{RetDelta}_t,\,
C_t,\,
\mathrm{CatErr}_t
\bigr),
\]
where \(U_t\) denotes adjudicable task utility, \(d'_t\) an oversight sensitivity measure, \(\mathrm{CommErr}_t\) commission error, \(\mathrm{RecLag}_t\) recovery lag, \(\mathrm{RetDelta}_t\) delayed retention or transfer degradation, \(C_t\) compute expenditure, and \(\mathrm{CatErr}_t\) catastrophic or governance-critical failure.

Let \(\mathfrak{G}\) denote the family of theorem-facing evaluation targets. We require the observation map to be **claim-sufficient** for \(\mathfrak{G}\): for every \(\Gamma\in\mathfrak{G}\), there exists a measurable map \(\psi_\Gamma\) such that
\[
\Gamma_t = \psi_\Gamma\!\bigl(\mathcal{M}(x_t,a_t,o_t,y_t)\bigr).
\]
Claim-sufficiency does not require \(\mathcal{M}\) to be injective in latent state. It requires only that admissible evaluation targets factor through observable anchors. This is what turns the control objective into an empirically anchorable object rather than a purely latent narrative.

The observation map induces a concrete correspondence between control losses and admissible anchors.

| Control quantity | Primary observable anchors | Typical role in evaluation |
|---|---|---|
| \(\ell_{\mathrm{task}}\) | \(U_t\), task error, delayed task success | Task utility / accuracy |
| \(\ell_{\mathrm{ovr}}\) | \(d'_t\), \(\mathrm{CommErr}_t\), checkability | Oversight quality |
| \(\ell_{\mathrm{intg}}\) | \(\mathrm{CommErr}_t\), \(\mathrm{RecLag}_t\), \(\mathrm{RetDelta}_t\) | Integrity preservation / overreliance control |
| \(\ell_{\mathrm{int}}\) | interaction count, verification burden, response compression, local friction | Interaction burden |
| \(\ell_{\mathrm{gov}}\) | \(\mathrm{CatErr}_t\), auditability, safe-mode entry, refusal/defer events | Governance and safety |

This table does not make the latent state observable. It makes the evaluation target-space explicit. The framework earns empirical content only to the extent that its loss terms are reported through these or equally strong anchors.


### 3.7 Regime partition

To capture the fact that more deviation does not always imply more help, we define a regime partition over the slow surrogate \(d_k^{\mathrm{eff}}\). Let
\[
r_k \in \{\mathrm{L},\mathrm{M},\mathrm{E}\}
\]
denote low, mid, and extreme regimes with hysteretic thresholds
\[
\theta_1^\uparrow > \theta_1^\downarrow,\qquad
\theta_2^\uparrow > \theta_2^\downarrow.
\]

The interpretation is:

- \(\mathrm{L}\): near-corridor regime; avoid unnecessary intrusion;
- \(\mathrm{M}\): moderate deviation; increase assistance and verification;
- \(\mathrm{E}\): extreme deviation; reduce branching and information bandwidth, increase conservatism.

### 3.8 Assumptions

We work under the following assumptions.

**A1 (Partial observability).** The latent state \(x_t\) is not directly observable.

**A2 (Bounded local operator-response sensitivity).** For each task mode \(\tau\), the relevant closed-loop state update is locally Lipschitz on the operating region. In Case C this is the component dynamics \(f_\tau\); in Case S it is an **admitted** reduced scalar routing model \(F_d\in\mathfrak{F}_d\). The scalar form is not assumed to inherit its constants from the component model unless Case C is active; it is a separately checkable empirical assumption on the reduced surrogate and must be supported by a local-gain certificate on held-out windows:
\[
\|f_\tau(x,a,e)-f_\tau(x',a',e)\|
\le
L_x\|x-x'\| + L_a\|a-a'\|,
\]
or, in the scalar-safe case,
\[
|F_d(d,\bar a,\bar e)-F_d(d',\bar a',\bar e')|
\le
L_d|d-d'| + L_{\bar a}\|\bar a-\bar a'\| + L_{\bar e}\|\bar e-\bar e'\|.
\]
Admission of \(F_d\) therefore carries both a model-class burden and a validation burden. If the local-gain certificate or envelope diagnostics fail, A2 must be treated as violated and the controller must downgrade, revalidate, or enter safe mode.

**A3 (Bounded policy gain).** The fast and slow policy maps are Lipschitz on the operating region with gains \(K_f\) and \(K_s\).

**A4 (Switching penalty bound).** Under admissible switching, the aggregate state perturbation due to a regime transition is bounded by \(\Delta_{\mathrm{sw}}\).

**A5 (Verification saturation; empirical shape assumption).** For admissible task classes, verification benefit is increasing and concave beyond a task-dependent threshold.

**A6 (Overload curvature; empirical shape assumption).** For admissible task classes, overload or interaction cost is convex in information bandwidth beyond a regime-dependent threshold.

**A7 (Anchor adjudicability).** For at least a subset of tasks, task utility and oversight outcomes are externally adjudicable.

**A8 (Optional physiology).** The controller remains well-defined when physiology is absent, invalid, or masked by signal-quality checks.

**A9 (Calibration window stability).** Task-conditional normalization constants remain approximately stable over the calibration window used to estimate them; if not, the controller must trigger revalidation or enter safe mode.

**A10 (Envelope detectability).** Persistent violations of A2 or A9 induce detectable changes in prediction residuals, empirical local gain, or calibration-drift statistics within a finite monitoring window.

Assumptions A5–A6 are modeling priors rather than universal behavioral laws. They are broadly consistent with cognitive load theory, automation complacency, and supervisory-control overload literatures [@sweller1988clt; @parasuraman2010complacency; @narayanan2026oversight], but are not derived from them. A9–A10 are operationally heavy rather than cosmetic: they determine whether the controller can recognize when its own local-stability story is no longer credible.

## 4. Routing Architecture

The architecture is intentionally narrower than the formal setup. Its purpose is only to show how CABDI is operationalized as a compact supervisory routing stack. Implementation-specific actuator mappings, estimator variants, and engine knobs are deferred to appendices so that the main paper remains theorem-first rather than plumbing-heavy.

### 4.1 Minimal supervisory stack

The controller is decomposed into four coupled modules:

1. a state-estimation layer producing behavior-first fast and slow surrogates;
2. a fast interaction layer controlling interruption, compression, and local friction;
3. a slow routing layer controlling regime, compute, and global verification;
4. a supervisory admissibility layer enforcing safety, fallback, and tier validity.

Formally,
\[
\hat x_t = \mathcal{E}(o_{1:t}),
\qquad
\nu_t^f = \pi_f(z_t^f,r_k,R_t),
\qquad
\nu_k^s = \pi_s(d_k^{\mathrm{eff}},R_k),
\]
with
\[
a_t = \pi_{\mathrm{safe}}(\nu_t^f,\nu_k^s,\hat x_t,R_t,s_t,q_t).
\]
The fast layer reacts to local interaction conditions; the slow layer changes the operating regime and compute or verification contract; the supervisory layer decides whether the proposed action is admissible at all.

### 4.2 Admissibility filter, diagnostics, and envelope-safe mode

No routing action is applied directly. The admissibility filter enforces at minimum
\[
\|u_t-u_{t-1}\|\le \delta_u,
\qquad
|C_{k+1}-C_k|\le \delta_C,
\]
as well as hysteretic regime switching, minimum dwell time, risk-tier vetoes, and fallback under low-confidence estimation. CABDI couples these hard guards to online envelope diagnostics aimed at A2 and A9. A minimal diagnostic stack is
\[
r_t^{\mathrm{pred}} = \|\hat z_{t+1|t}^f - z_{t+1}^f\|,
\qquad
r_t^{\mathrm{gain}} = \frac{|z_{t+1}^f-z_t^f|}{\varepsilon+\|u_t-u_{t-1}\|},
\]
\[
r_k^{\mathrm{cal}} = \max\!\Bigl\{
\|\hat\mu_{\tau,k}-\hat\mu_{\tau,k-1}\|,
\|\hat D_{\tau,k}-\hat D_{\tau,k-1}\|,
\mathrm{Err}_{H\text{-step},k}
\Bigr\}.
\]
Persistent residual inflation, gain inflation, rollout-error inflation, or calibration drift triggers envelope-safe mode:
\[
r_k\leftarrow \mathrm{E},\qquad
C_k\leftarrow C_{\mathrm{chk}},\qquad
v_k^{\mathrm{glob}}\leftarrow v_{\max},\qquad
s_t\leftarrow 0,
\]
while parameter adaptation is frozen and switching is suppressed for at least one dwell window. If outputs are not checkable under the resulting contract, the system must defer or refuse.

### 4.3 Tier validity, personalization, and governed engines

Tier management is part of the scientific contract of the framework. If signal quality collapses, the controller must fall back to behavior-only routing without changing the admissible claim class. Richer tiers may improve estimation, but they may not silently contaminate Tier-0 claims. Any downgrade from Tier 2 or Tier 1 to Tier 0 restores the last validated Tier-0 checkpoint, freezes richer-tier heads, and reopens Tier-0 adaptation only after explicit revalidation. When active-parameter uncertainty is large, the controller reverts to conservative defaults. One-size-fits-all routing is treated here as a failure mode, not as a neutral baseline.

CABDI is model-agnostic with respect to the governed engine. It can sit above a simple assistant, a retrieval-augmented system, or a bounded-search dual-process engine. The only requirement is that the engine expose controllable knobs corresponding to compute, branching, verification, and output shape. CABDI is therefore not a new model family. It is a theory of how to govern existing model families once they are placed inside a partially observed human interaction loop.

## 5. Theoretical Results

We now state the central main-text results supporting CABDI as a constrained routing theory rather than as a conceptual architecture. The confidence-gated safe-reduction bound and the compute-duality note remain in the appendices as supporting lemmas. In the present version, the practical-stability statement is treated explicitly as a **supporting proposition** for an admitted reduced-model family, while the non-monotonicity result remains the main structural theorem.

### 5.1 Proposition 1: Practical stability over an admitted bounded-sensitivity operator-response class

**Proposition 1 (Practical stability in the scalar-safe primary case over an admitted bounded-sensitivity operator-response class).** Consider Case S from Section 3.4, with slow latent routing state
\[
d_{k+1}^\star = F_d(d_k^\star,\bar a_k,\bar e_k) + \omega_k^d,
\qquad
\bar a_k=(r_k,C_k,v_k^{\mathrm{glob}},m_k),
\]
where \(F_d\in\mathfrak{F}_d\) is an admitted reduced slow routing model satisfying the scalar form of A2 on the operating region. Let \(\sigma(k)\) denote the regime-switching signal and assume an average dwell-time condition
\[
N_\sigma(k_0,k) \le N_0 + \frac{k-k_0}{\tau_a},
\]
where \(N_\sigma(k_0,k)\) is the number of slow regime switches on \([k_0,k)\), \(N_0\ge 0\), and \(\tau_a>0\). Suppose moreover that admitted slow actions obey rate limits and that the switching penalty satisfies
\[
L_d + L_{\bar a}K_s + \frac{\Delta_{\mathrm{sw}}}{\tau_a} < 1.
\]
Then there exists \(\eta_0>0\) and a compact neighborhood \(\mathcal{B}_d\subset[0,1]\) of the operating point \(d^\star\) such that, for this modeled interaction class, the Lyapunov candidate
\[
V_k = |d_k^\star-d^\star|^2 + \eta_0\|\bar a_k-\bar a^\star(d_k^\star)\|^2
\]
satisfies
\[
\mathbb{E}[V_{k+1}-V_k] < 0
\qquad \text{for } d_k^\star \notin \mathcal{B}_d,
\]
and hence the scalar-safe closed loop is practically stable for the admitted model class. The claim is not a guarantee for arbitrary human dynamics; it is a model-class result whose burden is carried by A2, A3, A4, A9, admission of \(F_d\), and the runtime envelope diagnostics.

*Interpretation.* This proposition is intentionally modest. It is a supporting control result about a validated reduced surrogate family, not a theorem about arbitrary human dynamics. Its role is to show that CABDI’s scalar-safe controller can be made internally coherent once the reduced slow model is admitted and monitored.

### 5.2 Empirical motivation for non-monotone assistance regimes

The non-monotone policy result is not motivated by theory alone. Recent empirical work across consulting, customer support, coding, education, and decision support increasingly suggests that assistance gains are regime-dependent rather than monotone. Field evidence on the jagged technological frontier shows that AI assistance can improve speed and quality on some realistic knowledge-work tasks while degrading correctness on nearby tasks that sit outside the model's reliable frontier [@dellacqua2023jagged]. Large-scale deployment evidence similarly shows heterogeneous gains across workers, including small quality declines among the highest-skill strata even when average productivity rises [@brynjolfsson2025work]. Together with the broader meta-analytic literature on when human-AI combinations help or fail [@vaccaro2024meta], these findings point in the same direction: additional assistance can improve performance in one region of the state space and degrade it in another.

CABDI does not claim that all assistance is non-monotone. It claims that there exists an empirically meaningful admissible class in which the monotone rule “more deviation implies more help” is structurally wrong. This empirical bridge matters because it turns Theorem 1 from a merely possible pathology into a formalization of a pattern that is already visible across multiple human-AI domains.

### 5.3 Theorem 1: Existence of non-monotone optimal assistance regimes

**Theorem 1 (Existence of non-monotone optimal routing over admissible task classes).** Let \(h\in[0,h_{\max}]\) denote scalar assistance intensity inside a fixed routing family for a task class \(\tau\) and risk tier \(R\). Consider the reduced objective
\[
J(h;d,R) = B(h,d,R) - O(h,d,R) - Q(h,d,R),
\]
where \(d\in[0,1]\) is the slow effective deviation proxy. Assume:

1. \(B,O,Q\) are twice continuously differentiable in \(h\) and \(d\);
2. for moderate \(d\), \(B\) is increasing and concave in \(h\);
3. for sufficiently large \(d\), \(O\) is convex in \(h\) and \(\partial_h O\) increases with \(d\);
4. catastrophic-risk term \(Q\) has positive cross-partial \(\partial_{hd}^2 Q > 0\) beyond a threshold \(d_c\);
5. the feasible set admits interior optima and standard regularity conditions for the first-order system.

Then there exist admissible problem classes and thresholds \(0<d_1<d_2\le 1\) such that an optimal assistance policy \(h^\star(d)\) is weakly increasing on \([0,d_1]\) and weakly decreasing on \([d_2,1]\). In particular, optimal assistance is generically non-monotone over that admissible class.

*Interpretation.* This is the main structural theorem of the paper. It does **not** say that all human-AI tasks are non-monotone. It says there exists an empirically meaningful admissible class in which “more deviation implies more help” is provably wrong.

### 5.4 Proposition 2: Claim-admissibility boundary under partial observability

**Proposition 2 (Observation-map sufficiency bounds admissible claims).** Let
\[
\mathcal{F}_{\mathrm{obs}}
=
\sigma\bigl(\{b_t,p_t,e_t,q_t,a_t,y_t\}_{t=1}^T\bigr)
\]
be the observable \(\sigma\)-algebra generated by behavioral traces, optional physiology, task evidence, signal quality, realized actions, and adjudicable outcomes. Let \(\mathfrak{G}\) denote the family of theorem-facing targets and suppose the observation map \(\mathcal{M}\) from Section 3.6 is claim-sufficient for \(\mathfrak{G}\). Let \(M_1\) and \(M_2\) be two latent-state model instantiations. If
\[
P_{M_1}\!\restriction_{\mathcal{F}_{\mathrm{obs}}}
=
P_{M_2}\!\restriction_{\mathcal{F}_{\mathrm{obs}}},
\]
then for every \(\Gamma\in\mathfrak{G}\),
\[
\Gamma(M_1)=\Gamma(M_2).
\]
Hence no theorem-facing claim about the unique semantic meaning of the latent regime variable is identifiable from the present framework alone. Only targets that factor through \(\mathcal{M}\) are admissible without additional evidence.

## 6. Identifiability and Claim Admissibility

The central epistemic risk in this domain is not only poor performance, but claim inflation: treating a useful routing surrogate as though it were a fully identified semantic state. CABDI addresses this risk by distinguishing control usefulness from semantic identifiability. These are related but not interchangeable properties.

### 6.1 Observable target space

Let
\[
\mathcal{F}_{\mathrm{obs}}=
\sigma\bigl(\{b_t,p_t,e_t,q_t,a_t,y_t\}_{t=1}^T\bigr)
\]
be the observable \(\sigma\)-algebra. An empirical routing claim is admissible only if its target can be written as an \(\mathcal{F}_{\mathrm{obs}}\)-measurable functional,
\[
\Gamma = \Phi\bigl(P_\pi(b_{1:T},p_{1:T},e_{1:T},q_{1:T},a_{1:T},y_{1:T})\bigr),
\]
possibly after nuisance adjustment, matched-budget conditioning, or task-family stratification.

Observable routing targets therefore include task-level utility, oversight sensitivity, commission-error rates, recovery lag, retention or transfer effects, compute expenditure, switching statistics, fallback rates, and safety-violation frequencies. These are the strongest claims of CABDI because they survive without privileged interpretation of latent state.

The admissible target set depends on adjudication availability. Under **full adjudication**, task utility, oversight sensitivity, commission errors, recovery lag, and delayed-retention targets may all enter \(\mathfrak{G}\). Under **partial adjudication**, delayed or sparse outcome variables may drop out while checkable utility, switching statistics, fallback rates, and compute-governance targets remain admissible. Under **no adjudication**, the framework contracts further: one may still evaluate compute discipline, switching behavior, fallback activation, and other mechanism-facing observables, but one may not elevate them into claims about improved correctness, oversight quality, or long-horizon integrity without additional evidence. Claim-sufficiency is therefore stratified by what parts of \(y_t\) are actually observed.

### 6.2 Metric identifiability versus semantic identifiability

The present framework does not require that latent operator variables be semantically identified in a strong psychological sense. For routing, the more relevant question is whether there exists a functional of the latent state that is stable enough under observational equivalence to support control. Recent identifiability work suggests that even when latent coordinates are not uniquely recoverable, relational or metric properties of latent geometry may remain identifiable [@syrota2025metric]. CABDI's scalar-safe surrogate is best interpreted in that spirit.

Accordingly, the scalar-safe layer should not be read as a hidden claim that a unique internal regime variable has been recovered. It should be read as a metric-identifiable control proxy: a reduced functional whose admissibility depends on observable-anchor sufficiency, invariance under latent reparameterization at the level relevant for routing, and measurable incremental value in downstream control. This interpretation strengthens the theory by narrowing what the scalar proxy is supposed to mean.

### 6.3 Behaviorally identifiable claim class

A claim is behaviorally identifiable if it is determined by the observable law induced by a policy over \(\mathcal{F}_{\mathrm{obs}}\). This class includes claims such as:

- whether a routing policy improves task utility under matched compute;
- whether it lowers commission errors or recovery lag;
- whether it improves oversight sensitivity under specified risk tiers;
- whether it reduces catastrophic or governance-relevant failures;
- whether its interaction burden remains within a prespecified envelope.

These are the strongest claims of the framework because they can be evaluated from behavior, task structure, and adjudicated outcomes alone.

### 6.4 Physiology-dependent claim class

Physiology-dependent claims belong to a weaker class. They are admissible only as **incremental-value** statements of the form:

1. a physiology-aware estimator improves a measurable routing target;
2. the improvement persists under matched compute, matched verification, and matched risk conditions;
3. the improvement survives comparison against strongest behavior-only baselines;
4. the sensing pipeline satisfies explicit quality and artifact checks.

This means that “EEG+ET improved routing utility by \(\Delta U\) over a behavior-only baseline under matched budgets” is admissible, while “the measured variable is the true cognitive phase” is not.

### 6.5 Claim ladder

The framework therefore distinguishes the following levels.

**L0 — Observable performance claims.** Improvements in task utility, oversight, safety, interaction burden, or compute discipline.

**L1 — Observable mechanism claims.** Changes in switching rate, fallback frequency, or verification use induced by the policy.

**L2 — Model-internal control claims.** Statements about how the controller behaves on the modeled operator-response class.

**L3 — Incremental sensing claims.** Physiology improves observable routing targets over strongest non-physiology baselines.

**L4 — Excluded semantic claims.** Unique latent-state semantics, privileged cognitive truth, or ontology-laden interpretations not broken open by additional interventions.

This ladder is not a rhetorical flourish. It is the mechanism by which the paper keeps its strongest claims aligned with what can actually be observed.

### 6.6 What would break observational equivalence?

Observational equivalence can be weakened by interventions that change the admissible evidence set. In principle, this may include randomized sensor ablation, causal manipulations of assistance structure, richer external labels, or stronger mechanistic constraints on the sensor model. But these are not assumed by default in the present paper. Hence the burden of proof lies on any stronger physiology-centered interpretation, not on the behavior-only theorem layer.

## 7. Falsification-First Evaluation Protocol

### 7.1 Staged evaluation principle

The evaluation story is intentionally staged. A believable first empirical paper should stop at Tier 0 or Tier 1 unless there is already strong evidence that the behavior-first controller is viable. The theorem layer is scalar-safe and behavior-first, so physiology is not required to make CABDI scientifically testable. Richer multimodal branches are extensions with higher evidentiary burden, not mandatory entry conditions.

### 7.2 Minimal first validation: Tier 0 / Tier 1

A minimal CABDI validation uses behavior-only signals or light physiology on one primary adjudicable task family and, if claim scope is broader, one optional secondary family. The first paper should report a small set of load-bearing outcomes rather than a maximal battery. Minimum primary outcomes are:

- task utility or error;
- oversight quality through \(d'_t\) or commission error;
- one integrity or recovery target such as \(\mathrm{RecLag}_t\) or a delayed retention proxy;
- compute expenditure and verification burden;
- switching rate, fallback rate, and safe-mode frequency.

Runtime diagnostics are mandatory. Tier 0 or Tier 1 must report at least
\[
r_t^{\mathrm{pred}},\qquad r_t^{\mathrm{gain}},\qquad r_k^{\mathrm{cal}},
\]
with thresholds, exceedance frequency, and the fraction of episodes that triggered envelope-safe mode. This is how the paper’s A2/A9 story becomes falsifiable in deployment-like evaluation rather than remaining a static assumption list. A narrow, well-powered claim on one adjudicable family is preferable to a broad underpowered package.

### 7.3 Minimal pre-empirical sanity check: stylized synthetic simulation

Before real-world evaluation, the framework should survive a stylized synthetic sanity check on explicit operator-response dynamics. This is **not** empirical validation. It is an internal coherence test asking whether the regime logic behaves as intended on a simulator whose assumptions are completely exposed.

A minimal simulator uses a scalar slow deviation state \(d_k\), exogenous risk \(R_k\), three policy baselines (static help, monotone help, and CABDI regime routing), and observable anchors aligned with the main theorem-facing targets. In the companion script for this version, the stylized update takes the generic form
\[
d_{k+1}=\Pi_{[0,1]}\Bigl(\alpha d_k + \beta_R R_k + \beta_O\,\mathrm{Overload}(h_k,d_k) - \beta_S\,\mathrm{Support}(h_k,v_k,d_k) + \xi_k\Bigr),
\]
with task error, commission error, catastrophic error, recovery lag, and compute all generated from the same exposed slow state and routed action tuple. On this toy simulator, the CABDI regime policy reduces catastrophic-error rate and recovery lag relative to the monotone-help baseline at similar average compute cost, while keeping the theorem-facing observation layer entirely behavior-first. The precise values are reported in Appendix C together with the simulator equations and script path.

The point of this exercise is limited but useful: a routing theory that cannot survive its own stylized simulator is not ready for deployment-like testing.

### 7.4 Full long-horizon program

The long-horizon empirical program is broader than the minimal first paper. Once Tier 0 or Tier 1 viability is established, the full program may add:

- multiple adjudicable task families;
- delayed anchors such as retention, transfer, or deskilling-sensitive outcomes;
- subgroup and heterogeneity analyses;
- longitudinal calibration-drift analysis;
- stronger personalization and downgrade/revalidation studies.

This broader program is scientifically valuable, but it should not be used to blur the evidentiary line for the first believable paper.

### 7.5 Tier 2: optional incremental-sensing extension

Tier 2 asks the harder question: whether auxiliary physiological channels add routing value over a fully tuned Tier 0 or Tier 1 system. Physiology is successful only if it contributes incremental value under artifact-aware calibration, anti-leakage tier handling, privacy-preserving preprocessing, and matched budgets. Tier 2 therefore extends the minimal package with:

- ablation of physiology versus behavior-only CABDI;
- artifact-aware gating and missingness analysis;
- cross-tier downgrade tests showing that Tier-0 performance is preserved after richer-tier use;
- incremental value on admissible targets only.

Tier 2 is not allowed to rescue a weak Tier-0 or Tier-1 controller.

### 7.6 Baseline hierarchy and matched-budget discipline

For every reported gain, the comparison class must be explicit.

**Core baselines:** static assistance, behavior-only adaptive routing, and matched-compute adaptive control without CABDI-specific routing structure.

**Extended baselines:** human-only where appropriate, physiology-enhanced variants, and task-specific specialist heuristics.

Matched-budget discipline is mandatory. A routing improvement is not credited to CABDI if it disappears after conditioning on compute budget, verification budget, and risk tier.

**Criterion 4 (Matched-compute falsifiability).** Let \(\Delta_\Gamma\) be the observed performance difference on an admissible target \(\Gamma\) between CABDI and a baseline policy class \(\mathcal{B}\). If for every strongest non-CABDI adaptive baseline \(b\in\mathcal{B}\) matched on task family, compute budget, verification budget, and risk tier,
\[
\Delta_\Gamma(\pi_{\mathrm{CABDI}},b) \le \varepsilon_\Gamma,
\]
where \(\varepsilon_\Gamma\) is a pre-registered practical significance threshold, then the corresponding CABDI claim is not supported at the targeted level. This is an evidentiary rule for evaluation, not a new theorem.

### 7.7 Primary anchors and secondary collaboration descriptors


A minimal CABDI paper should clearly separate theorem-facing anchors from broader collaboration descriptors.

| Layer | Examples | Evidentiary role |
|---|---|---|
| Primary admissible anchors | task utility, \(d'_t\), commission error, recovery lag, retention proxy, compute, safe-mode frequency | load-bearing support for CABDI claims |
| Secondary collaboration descriptors | perceived interaction quality, cognitive synergy, user agency, ethical acceptability, workload self-report | descriptive support; should not outrank anchors |

This split allows CABDI to learn from broader brain-agent-collaboration framing without making its theorem layer depend on weakly anchored self-report constructs. Collaboration quality matters, but it sits below adjudicable anchors in the evidentiary hierarchy.

### 7.6 Task families, reporting requirements, and failure modes

A minimal CABDI paper may focus on one adjudicable task family. Broader claims should add a second family with meaningfully different error structure. Suitable families include structured reasoning tasks with verifiable answers, diagnosis-like or causal tasks where misleading assistance is plausible, and operational decision tasks with explicit loss functions and interpretable catastrophic errors.

A physiology-aware arm is admissible only if all of the following are reported:

- sensor tier and sensor technology,
- preprocessing and artifact-handling pipeline,
- privacy-minimization or local abstraction rule for physiological signals,
- signal-quality rejection criteria,
- missingness rate and fallback behavior,
- anti-leakage protocol for tier downgrades,
- matched-compute comparison to behavior-only CABDI,
- incremental effect on admissible targets.

The framework recommends pre-registering practical significance thresholds \(\varepsilon_\Gamma\) for each admissible target. This prevents post hoc claims based on negligible improvements that are statistically detectable only because of large sample sizes.

The following outcomes count as substantive failure modes and must be reported, not hidden in appendices:

- no improvement over the strongest behavior-only baseline,
- apparent improvement entirely explained by extra compute or extra verification,
- safety gains offset by unacceptable interaction burden,
- sensor-driven gains that vanish under artifact-aware filtering,
- frequent safe-mode activation indicating unstable envelope assumptions,
- subgroup harms or personalization failure.

## 8. Discussion and Limitations

The main limitation of CABDI is not that it models too little, but that some of its strongest formal objects remain only partially anchored in real operator dynamics and feedback structure. The framework should therefore be interpreted as a disciplined control formalism with explicit failure modes, not as a validated general theory of human internal state.

### 8.1 What is genuinely strong in the current paper

The strongest parts of CABDI are:

1. the compression of the problem around a single constrained partially observable routing object;
2. the non-monotonicity result, which blocks naive adaptive-help intuition;
3. the admissibility boundary, which prevents drift into underidentified cognitive rhetoric;
4. the falsification-first evaluation discipline.

These are the parts most likely to survive even if specific proxy constructions, sensing modalities, or task families change.

The common thread across these strengths is **epistemic discipline rather than richer sensing**. CABDI is strongest not where it measures more, but where it constrains what it may claim. The framework can benefit from better sensors, richer estimators, or stronger personalization, but those extensions do not strengthen the core theory unless they preserve the claim boundary and survive matched-budget scrutiny. This is the main defensive argument of the paper: its scientific value comes first from disciplined routing claims, and only second from any optional sensing advantage.

### 8.2 Where the framework is still fragile

The strongest practical vulnerability of the framework is not the absence of physiology. It is the fragility of proxy design and operator modeling. A behavior-only or biobehavioral estimator may drift under task shift, suffer from scale mismatch across operators, or silently collapse into a proxy for generic difficulty rather than routing-relevant state. Feature choice, calibration constants, missingness handling, and aggregation across fast and slow loops are therefore not implementation details. They are part of the operational validity of the framework.

The physiology branch is fragile for a different reason: signal quality. Wearable EEG remains sensitive to electrode choice, motion, and artifact structure, while multimodal gains can disappear if preprocessing, gating, fallback logic, and anti-leakage revalidation are weak [@arpaia2025wearable; @bayat2026eeg; @rivasvidal2026eeget]. CABDI handles this by demoting physiology from theorem foundation to optional auxiliary sensor, but that move also means the theorem layer is intentionally more behavioral than the brand name might first suggest.

### 8.3 Which theorem is most likely to fail first

If the framework fails under real deployment, the earliest pressure is unlikely to fall on the supporting safe-reduction lemma or the compute-duality note relegated to the appendices. It is more likely to fall on the *instantiation* of the non-monotonicity result, because that result depends on empirical shape assumptions about overload curvature and verification benefit that may vary sharply across tasks and operators.

A second likely stress point is the stability theorem when human response sensitivity becomes highly nonlinear, strategic, or adversarial. The theorem remains useful as a model-class result, but real deployment may violate the bounded-sensitivity envelope more quickly than a formal analysis suggests. This is why runtime envelope diagnostics and safe-mode activation are part of the framework rather than post hoc engineering extras.

### 8.4 No direct claim of internal cognitive truth

The framework does not prove that any physiology-derived or criticality-inspired variable corresponds to the true internal regime of the operator. At most, such a variable is a useful observation channel whose legitimacy depends on incremental predictive or control value. This limitation is not peripheral. It is the central condition under which the paper avoids sliding from control theory into overclaimed cognitive ontology.

### 8.5 What CABDI is not

CABDI is not a theory of cognitive truth. It is not a proof that physiology is necessary for adaptive routing. It is not a general claim of latent-state recoverability under partial observability. And it is not a validated deployment result. It is a constrained control framework whose strongest branches live on behaviorally anchorable routing, oversight, integrity, and governance outcomes, and whose stronger physiology-facing branches remain conditional on incremental value, matched budgets, and anti-leakage discipline.

### 8.6 Relationship to existing control and POMDP theory

CABDI should be read as a structured synthesis, not as a claim that constrained partially observable control theory was missing until now. Its novelty lies in the domain compression and epistemic discipline: explicit operator-response dynamics, routing-centric action semantics, integrity-aware losses, biobehavioral observation tiers, and claim-admissibility constraints inside one object. CABDI does not claim a general reduction in worst-case constrained POMDP complexity. Its more modest claim is that the factorized observation model and separable routing losses motivate structured approximations—such as blockwise or point-based belief updates over routing-relevant subspaces—rather than generic unconstrained belief evolution. The paper’s value therefore lies in the disciplined assembly of these components into a more falsifiable theory of human–AI routing, not in any claim that each formal ingredient is individually unprecedented.

## 9. Conclusion

CABDI reframes human–AI interaction as a constrained routing problem under partial observability, bounded resources, and measurement uncertainty. Its central claim is not that physiology reveals cognitive truth, nor that more adaptive help is always better. Its stronger claim is more modest and more defensible: a human–AI system should decide when, how, and under what verification and compute contract to assist, and those decisions can be modeled as a constrained partially observable control problem with admissible empirical targets.

The present version strengthens that claim in four ways. It makes the operator-response dynamics explicit. It aligns the bio-digital layer with signal-processing reality by treating physiology as an optional, artifact-aware auxiliary channel. It grounds routing surrogates in outcome-conditioned oversight and strain indicators rather than in semantically ambiguous raw counts. And it positions the framework directly against constrained POMDP, belief-state, and trust-aware planning traditions rather than floating beside them.

What the paper offers, then, is not a completed empirical theory of physiology-driven interaction. It is a disciplined control-theoretic framework with clear failure conditions. If behavior-only routing saturates the gains, if physiology adds no incremental value under matched compute and risk, or if the reduced surrogate fails to support practical control under feedback scarcity, the stronger branches of the framework should be rejected. CABDI is not a theory of internal cognitive truth and not a proof that sensing more is inherently better. It is strongest where it claims less while still retaining routing value. That is exactly the asymmetry a serious preprint should want.

## Appendix A. Assumption Burden Table

| Assumption | Type | Burden | Why it matters |
|---|---|---|---|
| A1 Partial observability | Structural | Moderate | Core to the formal class |
| A2 Bounded local response sensitivity | Structural | High | Needed for practical stability |
| A3 Bounded policy gain | Structural | Moderate | Controls actuation amplification |
| A4 Switching penalty bound | Structural | Moderate | Makes dwell-time reasoning explicit |
| A5 Verification saturation | Empirical shape | High | Needed for non-monotonicity |
| A6 Overload curvature | Empirical shape | High | Needed for non-monotonicity |
| A7 Anchor adjudicability | Measurement | Moderate | Needed for admissible evaluation |
| A8 Optional physiology | Measurement | Low | Preserves behavior-first theorem layer |
| A9 Calibration window stability | Operational | High | First line of failure under task shift |
| A10 Envelope detectability | Operational | High | Needed for runtime diagnosis of A2/A9 failure |

## Appendix B. Formal Notes and Proofs

### B.1 Supporting Safe-Reduction Lemma

The confidence-gated safe-reduction bound used by the scalar-safe controller follows immediately from Lipschitz continuity of \(g\) and the triangle inequality applied to
\[
d_k^{\mathrm{eff}}-d_k^\star
=
\kappa_k(\hat d_k-d_k^\star) + (1-\kappa_k)(d_{\mathrm{safe}}-d_k^\star).
\]
This yields the stated upper bound immediately.

### B.2 Proof of Proposition 1

Let
\[
e_k = d_k^\star-d^\star,
\qquad
\nu_k = \bar a_k-\bar a^\star(d_k^\star),
\qquad
V_k = |e_k|^2 + \eta_0\|\nu_k\|^2.
\]
Because \(F_d\in\mathfrak{F}_d\) is admitted, A2 gives local constants \(L_d,L_{\bar a},L_{\bar e}\) on the operating set together with holdout and envelope checks. Writing the slow update relative to the operating point and using the fact that \(\bar a^\star(d)\) is locally Lipschitz with gain at most \(K_s\), we obtain
\[
|e_{k+1}|
\le
L_d|e_k| + L_{\bar a}\|\nu_k\| + \tfrac{\Delta_{\mathrm{sw}}}{\tau_a} + \zeta_k,
\]
where \(\zeta_k\) collects bounded disturbance, bounded exogenous slow evidence, and the finite-rate switching residue under average dwell time. Squaring both sides and absorbing cross terms with Young’s inequality yields constants \(c_1,c_2,c_3>0\) such that
\[
\mathbb{E}|e_{k+1}|^2 \le c_1 |e_k|^2 + c_2 \|\nu_k\|^2 + c_3.
\]
The admitted slow policy obeys rate limits and bounded gain, so there exists \(\bar c_1,\bar c_2,\bar c_3>0\) with
\[
\mathbb{E}\|\nu_{k+1}\|^2 \le \bar c_1 |e_k|^2 + \bar c_2 \|\nu_k\|^2 + \bar c_3.
\]
Choosing \(\eta_0>0\) small enough and combining the two inequalities gives
\[
\mathbb{E}[V_{k+1}\mid \mathcal{F}_k]
\le
\rho V_k + c_3 + \eta_0\bar c_3,
\]
with
\[
\rho < 1
\quad \text{whenever} \quad
L_d + L_{\bar a}K_s + \frac{\Delta_{\mathrm{sw}}}{\tau_a} < 1.
\]
Hence \(V_k\) is a stochastic Lyapunov function with negative drift outside a compact residual set determined by the bounded disturbance and switching residue. This proves practical stability for the admitted model class. The argument is intentionally local and conditional on admission of \(F_d\); it does not extend to arbitrary unvalidated human dynamics.

### B.3 Proof of Theorem 1

Define
\[
F(h,d) = \partial_h J(h;d,R) = \partial_h B(h,d,R)-\partial_h O(h,d,R)-\partial_h Q(h,d,R).
\]
By Assumption 1, \(F\) is continuously differentiable. By Assumption 5, interior optima satisfy \(F(h^\star(d),d)=0\) with \(\partial_{hh}^2 J(h^\star(d),d,R)<0\) on the admissible branch, so the implicit function theorem yields a locally unique differentiable optimizer branch
\[
\frac{dh^\star}{dd} = -\frac{\partial_{hd}^2 J}{\partial_{hh}^2 J}.
\]
Because \(\partial_{hh}^2 J<0\), the sign of \(dh^\star/dd\) is the sign of \(\partial_{hd}^2 J\).

For moderate \(d\), Assumption 2 implies that increasing assistance raises benefit while marginal overload and catastrophe terms remain weak. Hence there exists a nonempty interval \([0,d_1]\) on which
\[
\partial_{hd}^2 B > \partial_{hd}^2 O + \partial_{hd}^2 Q,
\]
and therefore \(\partial_{hd}^2 J>0\). Since the denominator is negative, \(dh^\star/dd\ge 0\) on that interval.

For sufficiently large \(d\), Assumptions 3 and 4 imply that marginal overload increases with \(d\) and the catastrophic-risk term becomes more help-sensitive. Therefore there exists \(d_2\in(d_1,1]\) such that for \(d\in[d_2,1]\),
\[
\partial_{hd}^2 O + \partial_{hd}^2 Q > \partial_{hd}^2 B,
\]
so \(\partial_{hd}^2 J<0\) and hence \(dh^\star/dd\le 0\) on that interval. Thus the optimal assistance branch is weakly increasing on \([0,d_1]\) and weakly decreasing on \([d_2,1]\). This proves existence of an admissible class with non-monotone optimal routing.

The theorem is existential rather than universal. It does not say every task family exhibits non-monotonicity. It says that once verification saturation, overload curvature, and catastrophe sensitivity coexist, monotone-help policies are structurally unjustified.

### B.4 Supporting Compute-Duality Note

The compute-contract note invoked in the architecture follows from standard convex duality. Under convexity and Slater feasibility, the Lagrangian
\[
\mathcal{L}(\pi,\eta)
=
\mathbb{E}_\pi\Big[\sum_k \bar\ell_k\Big]
+
\eta\left(
\mathbb{E}_\pi\Big[\sum_k C_k\Big]-\bar C
\right)
\]
satisfies strong duality. The optimal multiplier \(\eta^\star\) is the shadow price of compute.

### B.5 Proof of Proposition 2

Assume
\[
P_{M_1}\!\restriction_{\mathcal{F}_{\mathrm{obs}}}
=
P_{M_2}\!\restriction_{\mathcal{F}_{\mathrm{obs}}}.
\]
Let \(\Gamma\in\mathfrak{G}\). By claim-sufficiency of \(\mathcal{M}\), there exists an \(\mathcal{F}_{\mathrm{obs}}\)-measurable map \(\psi_\Gamma\) such that
\[
\Gamma = \psi_\Gamma\!\bigl(\mathcal{M}(x_{1:T},a_{1:T},o_{1:T},y_{1:T})\bigr).
\]
Because \(\mathcal{M}\) is \(\mathcal{F}_{\mathrm{obs}}\)-measurable, the random variable \(\Gamma\) is itself \(\mathcal{F}_{\mathrm{obs}}\)-measurable. Equality of the two restricted laws therefore implies equality of the pushforward laws of \(\Gamma\):
\[
P_{M_1}\circ \Gamma^{-1} = P_{M_2}\circ \Gamma^{-1}.
\]
Hence every admissible theorem-facing target has the same distribution under \(M_1\) and \(M_2\). In particular, any deterministic functional or population-level summary of \(\Gamma\) used by the paper — means, rates, matched-budget contrasts, or quantiles — is identical under the two models. Therefore no admissible theorem-facing claim can distinguish \(M_1\) from \(M_2\) beyond what is already contained in the observation map. Any residual difference between the models is semantic or latent-structural rather than theorem-facing. This is precisely the claim-admissibility boundary.

### B.6 Matched-Compute Criterion Note

This criterion is definitional but important. It makes the evidentiary rule explicit: no claim is supported unless its practical effect exceeds a pre-registered threshold after matching on compute, verification, and risk. This blocks post hoc attribution of gains that are actually due to hidden resource expenditure or weak baseline choice.

## Appendix C. Stylized Synthetic Sanity Check

### C.1 Purpose and scope

The synthetic simulation included in this version is a **sanity check**, not an empirical validation. Its role is to test whether the regime logic, observable anchors, and safe-mode story behave coherently on an explicit stylized operator-response model before any deployment-like experiment is attempted.

### C.2 Stylized simulator

The simulator uses a scalar slow deviation state \(d_k\in[0,1]\), an exogenous risk process \(R_k\in[0,1]\), and routed actions \((h_k,v_k)\) representing assistance intensity and verification depth. The slow update is
\[
d_{k+1}=\Pi_{[0,1]}\Bigl(0.70 d_k + 0.22R_k + 0.30\,\mathrm{Overload}(h_k,d_k) - 0.24\,\mathrm{Support}(h_k,v_k,d_k) + \xi_k\Bigr),
\]
with Gaussian noise \(\xi_k\). The simulator also emits theorem-facing observables: task error, catastrophic error, commission error, recovery lag, compute, and safe-mode frequency. Three baselines are compared:

1. **static help**: fixed \((h,v)\);
2. **monotone help**: assistance intensity increases monotonically with \(d_k\);
3. **CABDI regime**: low intrusion for low \(d_k\), structured assistance for moderate \(d_k\), and reduced bandwidth with high verification for extreme \(d_k\).

### C.3 Aggregate illustrative outputs

The companion script (`cabdi_v4_5_synthetic_sanity_check.py`) generates the following aggregate means over 8,000 simulated episodes:

| Policy | Task error | Cat. error | Comm. error | Recovery lag | Compute | Safe-mode freq. |
|---|---:|---:|---:|---:|---:|---:|
| Static help | 0.1911 | 0.00334 | 0.08515 | 0.11754 | 2.0350 | 0.00000 |
| Monotone help | 0.1973 | 0.00308 | 0.08518 | 0.10423 | 1.9342 | 0.00011 |
| CABDI regime | 0.1970 | 0.00259 | 0.08401 | 0.08553 | 1.9384 | 0.00015 |

The main qualitative point is that the CABDI regime policy improves catastrophic-error rate and recovery lag relative to the monotone-help baseline at similar compute cost. Because the simulator is stylized and favorable to the modeled assumptions, these numbers should not be interpreted as evidence about real deployment performance. Their function is only to show that the control logic is coherent enough to survive a transparent toy world.

## Appendix D. Implementation and Reporting Notes

### D.1 Observation Tiers and Estimator Families

CABDI supports three sensing regimes.

**Tier 0:** behavior-only. Suitable for theorem-layer validation and first empirical tests.

**Tier 1:** behavior + light physiology. Practical candidates include HRV and pupillometry, subject to quality checks.

**Tier 2:** behavior + light physiology + richer channels. EEG and EEG+ET belong here if electrode technology, artifact handling, and fallback logic are specified.

Recommended estimator families:

- behavior-only supervised or semi-supervised filters for \(z_t^f\);
- masked multimodal filters with explicit signal-quality gating for \(\hat x_t\);
- task-conditional calibration with periodic drift checks;
- outcome-conditioned feature construction for oversight signals;
- admitted reduced slow routing surrogates from \(\mathfrak{F}_d\) with holdout and local-gain certificates.

### D.2 Tiered Reporting Template

A minimum reporting template for empirical CABDI papers should include:

1. task families and adjudicability conditions;
2. policy class and action space actually implemented;
3. sensing tier and sensor technology;
4. preprocessing, signal-quality thresholds, and fallback rules;
5. calibration protocol for task-conditional statistics;
6. baseline hierarchy and matched-budget controls;
7. pre-registered practical thresholds \(\varepsilon_\Gamma\);
8. full failure reporting, including subgroup harms and null results.

This template is intentionally routing-specific rather than institutionally self-contained. It is compatible with broader reporting frameworks such as DECIDE-AI, REFORMS, and BetterBench, but adds requirements that those frameworks do not foreground: matched-compute baselines, envelope-safe diagnostics, tier-downgrade anti-leakage checks, admitted-reduced-model reporting, and mandatory physiology-as-incremental-value reporting.

## References
