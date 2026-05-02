# Tune Hub — Detailed Feature Implementation Plans
## For: RePrompt, Dictation, and Agent Tuners
### wiztant Platform | Desktop 1 + Desktop 2 Architecture

---

# SECTION 1: REPROMPT TUNER

## 1. Algorithm Design

### 1.1 Chosen Algorithm: Multi-Task Bayesian Optimization with Thompson Sampling

**Why this algorithm fits:**
- The parameter space is continuous (5-6 persona weights ∈ [0,1]) but bounded
- We need sample-efficient learning (expensive LLM calls)
- We have noisy, subjective feedback (human quality scores)
- Persona conflicts create a non-convex objective landscape
- We want to balance exploration vs. exploitation (Thompson Sampling)

**Algorithm stack:**
1. **Surrogate Model**: Gaussian Process (GP) with Matern-5/2 kernel
2. **Acquisition Function**: Expected Improvement (EI) with exploration parameter ξ=0.01
3. **Constraint Handling**: Linear constraints for conflicting personas
4. **Multi-Task Extension**: Task-clustered GPs sharing hyperparameters

### 1.2 Pseudocode — Core Learning Loop

```
CLASS RePromptTuner:
    
    INITIALIZE:
        personas = ["debug", "build", "research", "write", "plan"]
        conflict_matrix = {
            ("debug", "write"): 0.3,    # Cannot both be > 0.7
            ("build", "plan"): 0.25,   # Cannot both be > 0.8
            ("research", "build"): -0.1  # Synergy: boost if both > 0.4
        }
        gp_model = GaussianProcess(kernel="matern52", noise=0.1)
        observation_history = []
        task_classifier = TaskClassifier()
        
    FUNCTION learn_blend(task_prompt, task_type=None):
        # Step 1: Classify task if type not provided
        IF task_type IS None:
            task_type = task_classifier.classify(task_prompt)
            confidence = task_classifier.confidence
        ELSE:
            confidence = 1.0
            
        # Step 2: Check if we have enough data for this task cluster
        task_observations = FILTER observation_history BY task_cluster == task_type
        
        IF LENGTH(task_observations) < 3:
            # Warm-start with heuristic defaults
            candidate_weights = generate_heuristic_blend(task_type)
            RETURN run_experiment(task_prompt, candidate_weights, task_type)
        
        # Step 3: Fit GP on normalized weights → quality_score
        X = EXTRACT weights FROM task_observations  # Shape: (n, 5)
        y = EXTRACT quality_scores FROM task_observations  # Shape: (n,)
        
        # Add derived features: conflict penalties, synergy bonuses
        X_augmented = augment_with_interactions(X, conflict_matrix)
        gp_model.fit(X_augmented, y)
        
        # Step 4: Optimize acquisition function
        best_candidate = None
        best_acq_value = -INFINITY
        
        FOR i IN RANGE(100):  # Random restarts
            random_seed = random_weights_satisfying_constraints(conflict_matrix)
            candidate = optimize_lbfgs(
                objective = negative_expected_improvement,
                x0 = random_seed,
                bounds = [(0,1)] * 5,
                constraints = linear_conflict_constraints(conflict_matrix)
            )
            acq_val = expected_improvement(candidate, gp_model, best_observed=max(y))
            IF acq_val > best_acq_value:
                best_candidate = candidate
                best_acq_value = acq_val
                
        # Step 5: Run experiment with candidate blend
        result = run_experiment(task_prompt, best_candidate, task_type)
        RETURN result
    
    FUNCTION run_experiment(task_prompt, weights, task_type):
        # Generate 3 responses with different seeds using the blend
        responses = []
        FOR seed IN [42, 123, 999]:
            # Construct persona-weighted system prompt
            system_prompt = construct_weighted_prompt(weights, personas)
            response = llm_generate(
                model = "claude-sonnet-4-20250514",  # Primary model
                system = system_prompt,
                user = task_prompt,
                temperature = 0.7,
                seed = seed
            )
            responses.append(response)
        
        # Present to user for feedback
        quality_score = present_and_score(responses)  # User rates 0-1
        
        # Record observation
        observation = {
            "task_type": task_type,
            "task_embedding": embed(task_prompt),
            "weights": weights,
            "quality_score": quality_score,
            "responses": responses,
            "timestamp": now(),
            "model": "claude-sonnet"
        }
        observation_history.append(observation)
        
        RETURN {
            "weights": weights,
            "quality_score": quality_score,
            "best_response": SELECT_BEST(responses, quality_score)
        }
    
    FUNCTION construct_weighted_prompt(weights, personas):
        # Build system prompt that injects persona directives with weights
        directives = []
        FOR persona, weight IN ZIP(personas, weights):
            IF weight > 0.05:  # Threshold for inclusion
                directive = PERSONA_DIRECTIVES[persona]
                # Weight modulates directive strength
                intensity = INT(weight * 10)  # 1-10 scale
                directives.append(f"[{persona.upper()}:{intensity}] {directive}")
        
        base = "You are an AI assistant. Apply the following persona blend:\n"
        RETURN base + "\n".join(directives) + "\nBalance these directives according to their intensity ratings."
    
    FUNCTION expected_improvement(x, gp_model, best_observed, xi=0.01):
        mu, sigma = gp_model.predict(x, return_std=True)
        z = (mu - best_observed - xi) / sigma
        RETURN (mu - best_observed - xi) * CDF(z) + sigma * PDF(z)
```

### 1.3 Convergence Criteria

```
CONVERGENCE_CHECK(observation_history, task_type):
    recent = LAST_N(observation_history, 5) WHERE task_cluster == task_type
    
    # Criterion 1: Quality plateau
    IF STD(quality_scores of recent) < 0.05 AND MEAN(quality_scores) > 0.85:
        RETURN "CONVERGED_HIGH_QUALITY"
    
    # Criterion 2: Acquisition function flat
    last_acq_values = recent.acquisition_values
    IF MAX(last_acq_values) < 0.01:
        RETURN "CONVERGED_EXPLORATION_DONE"
    
    # Criterion 3: Weight stability
    IF STD(recent.weights across dimensions) < 0.08:
        RETURN "CONVERGED_WEIGHTS_STABLE"
    
    # Criterion 4: Budget exhausted
    IF count_observations(task_type) >= MAX_ITERATIONS_PER_TASK:
        RETURN "CONVERGED_BUDGET"
    
    RETURN "CONTINUE"
```

**Hyperparameters:**
| Parameter | Value | Rationale |
|-----------|-------|-----------|
| MAX_ITERATIONS_PER_TASK | 12 | Empirical: 90% convergence by iteration 10 |
| GP noise prior | 0.1 | Human feedback is noisy, subjective |
| EI exploration ξ | 0.01 | Small: prefer exploitation after 3 samples |
| Weight threshold | 0.05 | Ignore negligible persona contributions |
| Restart count | 100 | Ensure global optimization of acquisition |

---

## 2. Experimentation Protocol

### 2.1 Iteration Structure

| Phase | Iterations | Purpose | Budget |
|-------|-----------|---------|--------|
| Warm-start | 1-3 | Heuristic initialization | 3 × 3 responses = 9 LLM calls |
| Exploration | 4-8 | GP-guided diverse blends | 5 × 3 responses = 15 LLM calls |
| Exploitation | 9-12 | Converge on best region | 4 × 3 responses = 12 LLM calls |
| **Total** | **12** | | **36 LLM calls** |

### 2.2 Per-Iteration Detail

```
ITERATION_LOOP(task_prompt, task_type, max_iterations=12):
    
    FOR iteration IN 1..max_iterations:
        
        # Phase detection
        IF iteration <= 3:
            phase = "WARM_START"
            weights = heuristic_blend(task_type, iteration)
        ELSE IF iteration <= 8:
            phase = "EXPLORATION"
            weights = gp_acquisition_maximize(task_type, exploration_heavy=True)
        ELSE:
            phase = "EXPLOITATION"
            weights = gp_acquisition_maximize(task_type, exploration_heavy=False)
        
        # Response generation
        responses = []
        FOR model_config IN [
            {"model": "claude-sonnet", "provider": "anthropic"},
            {"model": "kimi-k2", "provider": "moonshot"},
            {"model": "claude-sonnet", "provider": "anthropic", "temperature": 0.9}
        ]:
            system_prompt = construct_weighted_prompt(weights)
            response = generate_with_timeout(
                model = model_config,
                system = system_prompt,
                user = task_prompt,
                timeout_sec = 30
            )
            responses.append({
                "text": response,
                "model": model_config.model,
                "weight_vector": weights
            })
        
        # Quality measurement (dual-mode)
        IF user_available AND iteration % 2 == 1:
            # Live user feedback every odd iteration
            quality_score = present_responses_to_user(responses)
            feedback_source = "human"
        ELSE:
            # Automated scoring on even iterations (or fallback)
            quality_score = automated_quality_score(responses, task_type)
            feedback_source = "automated"
        
        # Record
        record_observation(task_type, weights, quality_score, responses, feedback_source)
        
        # Check convergence
        status = CONVERGENCE_CHECK(observation_history, task_type)
        IF status.startswith("CONVERGED"):
            BREAK and store_final_blend(task_type, best_weights(), status)
    
    RETURN get_best_blend(task_type)
```

### 2.3 Automated Quality Scoring (Fallback)

When user is unavailable, use a reference LLM as judge:

```
FUNCTION automated_quality_score(responses, task_type):
    # Use a strong model to evaluate without persona bias
    judge_prompt = f"""
    Evaluate these {len(responses)} responses to a {task_type} task.
    Score each on: accuracy (0-1), completeness (0-1), clarity (0-1).
    Return ONLY a JSON object with scores.
    """
    
    scores = []
    FOR response IN responses:
        judge_output = llm_generate(
            model = "claude-opus",
            system = "You are an objective quality evaluator. Be strict.",
            user = judge_prompt + "\n\nResponse to evaluate:\n" + response.text,
            temperature = 0.0
        )
        parsed = parse_json(judge_output)
        composite = (parsed.accuracy + parsed.completeness + parsed.clarity) / 3
        scores.append(composite)
    
    RETURN MAX(scores)  # Take best of 3 as the blend's score
```

### 2.4 Credit Consumption Model

| Component | Calls/Iteration | Credits/Call | Iteration Cost | Total (12 iter) |
|-----------|----------------|--------------|----------------|-----------------|
| Response generation (3 models) | 3 | ~40 | 120 | 1,440 |
| User feedback iterations | 1.5 avg | 0 | 0 | 0 |
| Auto-judge (6 iterations) | 3 | ~50 | 150 | 900 |
| GP fitting + optimization | 1 | ~0.5 | 0.5 | 6 |
| **Total** | | | **~271/iter** | **~2,346** |

**Optimized target**: 1,500 credits via:
- Reduce to 2 responses/iteration after iteration 6 → saves ~480 credits
- Skip auto-judge after convergence detected → saves ~300 credits
- Use cheaper model (Haiku) for judge → saves ~400 credits
- **Optimized total: ~1,166 credits** (under 1,500 budget)

---

## 3. Data Collection & Feature Engineering

### 3.1 Raw Data Collected

```json
{
  "observation_id": "obs_2024_001",
  "timestamp": "2024-05-15T14:23:01Z",
  "session_id": "sess_abc123",
  
  "input": {
    "raw_prompt": "How do I fix this React useEffect memory leak?",
    "task_type": "coding_task",
    "task_type_confidence": 0.94,
    "prompt_embedding": [0.12, -0.34, ..., 0.89],
    "prompt_length": 45,
    "has_code_blocks": true,
    "language_detected": "javascript"
  },
  
  "experiment": {
    "iteration": 7,
    "phase": "exploration",
    "weight_vector": {
      "debug": 0.75,
      "build": 0.45,
      "research": 0.25,
      "write": 0.0,
      "plan": 0.10
    },
    "constraint_penalties": {
      "debug_write_conflict": 0.0,
      "build_plan_conflict": 0.0
    },
    "personas_active": ["debug", "build", "research", "plan"]
  },
  
  "output": {
    "responses": [
      {"model": "claude-sonnet", "text": "...", "latency_ms": 1200},
      {"model": "kimi-k2", "text": "...", "latency_ms": 900},
      {"model": "claude-sonnet-var", "text": "...", "latency_ms": 1150}
    ],
    "quality_score": 0.92,
    "feedback_source": "human",
    "user_comments": "Great explanation of cleanup functions"
  },
  
  "derived_features": {
    "weight_entropy": 1.23,
    "dominant_persona": "debug",
    "persona_concentration": 0.75,
    "conflict_severity": 0.0,
    "response_diversity": 0.34
  }
}
```

### 3.2 Feature Engineering Pipeline

```
FEATURE_EXTRACT(raw_prompt, weight_vector, responses):
    
    # Prompt features
    prompt_embedding = sentence_transformer.encode(raw_prompt)  # 384-dim
    prompt_length = len(raw_prompt.split())
    has_code = regex_contains(raw_prompt, "```")
    has_question = raw_prompt.endswith("?")
    language = detect_language(raw_prompt)  # fasttext
    
    # Weight vector features
    weight_entropy = -SUM(w * log(w) FOR w IN weights IF w > 0)
    dominant_persona = ARGMAX(weights)
    concentration = MAX(weights)
    active_count = COUNT(weights > 0.05)
    
    # Interaction features (capture synergy/conflict effects)
    interactions = []
    FOR (p1, p2), rule IN conflict_matrix:
        w1, w2 = weights[p1], weights[p2]
        IF rule > 0 AND w1 > 0.7 AND w2 > 0.7:
            interactions.append(rule * min(w1, w2))
        ELSE IF rule < 0 AND w1 > 0.4 AND w2 > 0.4:
            interactions.append(abs(rule) * min(w1, w2))  # synergy bonus
    
    # Response features
    response_diversity = 1 - average_cosine_similarity(responses)
    avg_length = MEAN(len(r) FOR r IN responses)
    
    RETURN CONCAT(prompt_embedding, [
        prompt_length, has_code, has_question, language_id,
        weight_entropy, concentration, active_count,
        SUM(interactions), response_diversity, avg_length
    ])
```

### 3.3 Task Classification (Context Detection)

```
CLASS TaskClassifier:
    
    # Pre-defined task clusters with seed examples
    TASK_CLUSTERS = {
        "coding_task": {
            "keywords": ["code", "bug", "error", "function", "class", "import", "debug"],
            "embeddings": [embed(seed) FOR seed IN coding_examples],
            "default_blend": {"debug": 0.7, "build": 0.5, "research": 0.2, "write": 0, "plan": 0.1}
        },
        "writing_task": {
            "keywords": ["write", "essay", "email", "blog", "draft", "tone", "style"],
            "embeddings": [embed(seed) FOR seed IN writing_examples],
            "default_blend": {"debug": 0, "build": 0.1, "research": 0.3, "write": 0.9, "plan": 0.2}
        },
        "research_task": {
            "keywords": ["research", "find", "analyze", "compare", "sources", "study"],
            "embeddings": [embed(seed) FOR seed IN research_examples],
            "default_blend": {"debug": 0.1, "build": 0, "research": 0.9, "write": 0.3, "plan": 0.2}
        },
        "planning_task": {
            "keywords": ["plan", "schedule", "roadmap", "steps", "organize", "timeline"],
            "embeddings": [embed(seed) FOR seed IN planning_examples],
            "default_blend": {"debug": 0.1, "build": 0.3, "research": 0.2, "write": 0.1, "plan": 0.9}
        },
        "building_task": {
            "keywords": ["build", "create", "implement", "setup", "configure", "deploy"],
            "embeddings": [embed(seed) FOR seed IN building_examples],
            "default_blend": {"debug": 0.3, "build": 0.8, "research": 0.2, "write": 0.1, "plan": 0.4}
        }
    }
    
    FUNCTION classify(raw_prompt):
        prompt_emb = embed(raw_prompt)
        
        # Method 1: Keyword match (fast)
        keyword_scores = {}
        FOR task, data IN TASK_CLUSTERS:
            matches = COUNT(kw IN raw_prompt.lower() FOR kw IN data.keywords)
            keyword_scores[task] = matches / len(data.keywords)
        
        # Method 2: Embedding similarity (accurate)
        embedding_scores = {}
        FOR task, data IN TASK_CLUSTERS:
            similarities = [cosine_similarity(prompt_emb, seed_emb) FOR seed_emb IN data.embeddings]
            embedding_scores[task] = MAX(similarities)
        
        # Ensemble: weighted combination
        final_scores = {}
        FOR task IN TASK_CLUSTERS:
            final_scores[task] = 0.3 * keyword_scores[task] + 0.7 * embedding_scores[task]
        
        best_task = ARGMAX(final_scores)
        confidence = final_scores[best_task] / SUM(final_scores)
        
        # If confidence < 0.4, return "general" with no strong blend
        IF confidence < 0.4:
            RETURN ("general", confidence)
        
        RETURN (best_task, confidence)
    
    FUNCTION confidence(self, task_type):
        RETURN self.last_confidence
```

---

## 4. Model Storage & Retrieval

### 4.1 Learned Model Schema

```json
{
  "model_version": "reprompt_v2.1",
  "created_at": "2024-05-15T18:00:00Z",
  "last_updated": "2024-05-20T09:30:00Z",
  
  "task_profiles": {
    "coding_task": {
      "task_id": "coding_task",
      "task_name": "Software Development & Debugging",
      "convergence_status": "CONVERGED_HIGH_QUALITY",
      "observation_count": 11,
      
      "best_blend": {
        "debug": 0.75,
        "build": 0.45,
        "research": 0.25,
        "write": 0.0,
        "plan": 0.10,
        "custom": 0.0
      },
      "quality_score": 0.94,
      "quality_std": 0.03,
      
      "blend_history": [
        {"iteration": 1, "weights": {...}, "score": 0.72},
        {"iteration": 2, "weights": {...}, "score": 0.81},
        ...
      ],
      
      "gp_hyperparameters": {
        "length_scale": [0.5, 0.3, 0.4, 0.8, 0.6],
        "signal_variance": 0.25,
        "noise_variance": 0.01
      },
      
      "confidence_metrics": {
        "convergence_iteration": 9,
        "exploration_coverage": 0.78,
        "last_acquisition_value": 0.003
      }
    },
    "writing_task": { ... }
  },
  
  "meta": {
    "total_observations": 47,
    "total_tasks_learned": 5,
    "credit_consumed": 1380,
    "average_convergence_iterations": 9.4
  }
}
```

### 4.2 Retrieval & Matching Logic

```
FUNCTION match_tune_to_request(prompt, available_tunes):
    
    # Step 1: Classify incoming prompt
    task_type, confidence = task_classifier.classify(prompt)
    
    # Step 2: Exact match
    IF task_type IN available_tunes AND confidence > 0.7:
        tune = available_tunes[task_type]
        IF tune.quality_score > 0.80:
            RETURN {
                "action": "APPLY_BLEND",
                "blend": tune.best_blend,
                "confidence": confidence * tune.quality_score,
                "source": "learned",
                "task_type": task_type
            }
    
    # Step 3: Fuzzy match via embedding similarity
    prompt_emb = embed(prompt)
    best_similarity = 0
    best_tune = None
    
    FOR task_id, tune IN available_tunes:
        # Use centroid of learned observations
        tune_centroid = tune.centroid_embedding
        similarity = cosine_similarity(prompt_emb, tune_centroid)
        IF similarity > best_similarity:
            best_similarity = similarity
            best_tune = tune
    
    IF best_similarity > 0.85 AND best_tune.quality_score > 0.75:
        RETURN {
            "action": "APPLY_BLEND",
            "blend": best_tune.best_blend,
            "confidence": best_similarity * 0.8,
            "source": "fuzzy_matched",
            "matched_task": best_tune.task_id
        }
    
    # Step 4: Fallback — use heuristic default
    default_blend = TASK_CLUSTERS[task_type].default_blend IF task_type IN TASK_CLUSTERS ELSE uniform_blend()
    
    RETURN {
        "action": "APPLY_DEFAULT",
        "blend": default_blend,
        "confidence": confidence * 0.5,
        "source": "heuristic",
        "trigger_learning": True
    }
```

### 4.3 Confidence Thresholds & Automatic Application

| Confidence Range | Action | User Notification |
|-----------------|--------|-------------------|
| > 0.90 | Auto-apply blend, no notification | Silent optimization |
| 0.75 - 0.90 | Apply blend, show "optimized for [task]" toast | Brief indicator |
| 0.60 - 0.75 | Apply blend but offer "try default" button | Reversible |
| 0.40 - 0.60 | Use default, trigger background learning | "Learning your style..." |
| < 0.40 | Use default, no learning trigger | No action |

### 4.4 Fallback Behavior

```
FUNCTION fallback_response(prompt, context):
    
    # No learned tune available
    IF context.trigger_learning:
        # Start background learning session
        background_session = RePromptTuner.start_session(prompt)
        RETURN {
            "response": generate_with_default_blend(prompt),
            "learning_session_id": background_session.id,
            "message": "I'm learning the best approach for this type of task. Please rate my response to help me improve."
        }
    ELSE:
        RETURN generate_with_default_blend(prompt)
```

---

## 5. Integration Points

### 5.1 TuneHub Base Class Interface

```python
class RePromptTuner(TuneHubBase):
    """
    Plugs into TuneHub via these hooks:
    """
    
    def __init__(self, hub_config):
        super().__init__(hub_config)
        self.gp_model = None
        self.observations = ObservationStore()
        self.classifier = TaskClassifier()
        
    def register_with_hub(self, hub):
        """Called by TuneHub during initialization"""
        hub.register_tuner(
            name="reprompt",
            trigger_events=["PROMPT_RECEIVED", "USER_FEEDBACK"],
            output_format="persona_blend",
            priority=1  # High: affects all responses
        )
    
    def on_event(self, event_type, payload):
        """Event handler called by TuneHub event bus"""
        
        IF event_type == "PROMPT_RECEIVED":
            # Return blend to use for this prompt
            match_result = self.match_tune_to_request(
                prompt=payload.text,
                available_tunes=self.get_all_tunes()
            )
            RETURN BlendEvent(blend=match_result.blend, source=match_result.source)
        
        IF event_type == "USER_FEEDBACK":
            # Record feedback for active learning loop
            active_session = self.get_session(payload.session_id)
            IF active_session:
                active_session.record_feedback(
                    quality_score=payload.rating,
                    comments=payload.comments
                )
                # Check if we should continue learning
                IF active_session.should_continue():
                    self.trigger_next_iteration(active_session)
        
        IF event_type == "RESPONSE_GENERATED":
            # Log for post-hoc analysis
            self.observations.log_response(payload)
    
    def get_learned_model(self):
        """Serialize current state for persistence"""
        RETURN self.serialize_gp_model() + self.observations.export()
    
    def load_learned_model(self, model_data):
        """Hydrate from stored model"""
        self.gp_model = deserialize_gp(model_data.gp_state)
        self.observations.import_(model_data.observations)
```

### 5.2 Desktop 1 vs Desktop 2 Responsibilities

| Responsibility | Desktop 1 (Main) | Desktop 2 (Isolated) |
|---------------|------------------|---------------------|
| User interaction | Full UI, prompt input, feedback collection | None (headless) |
| Blend application | Real-time prompt augmentation | Validation testing |
| GP optimization | Lightweight (100 restarts) | Heavy batch experiments |
| Model persistence | SQLite + file system | Backup mirror |
| Response generation | Primary (Kimi, Claude APIs) | Validation only |
| Credit tracking | Primary ledger | Sub-account for experiments |

```
# Desktop 2 validation pipeline
FUNCTION validate_on_desktop2(tune_candidate):
    # Run the same prompt 5 times with learned blend on Desktop 2
    # Compare against default blend
    results = desktop2.run_batch(
        prompt_suite=VALIDATION_SUITE,
        blend=tune_candidate.best_blend,
        default_blend=DEFAULT_BLEND,
        iterations=5
    )
    
    # Statistical test: is learned blend significantly better?
    improvement = wilcoxon_signed_rank_test(results.learned_scores, results.default_scores)
    
    IF improvement.p_value < 0.05 AND improvement.effect_size > 0.3:
        RETURN "VALIDATED"
    ELSE:
        RETURN "REJECTED: insufficient improvement"
```

### 5.3 APIs Needed from Other wiztant Features

| Feature | API | Purpose |
|---------|-----|---------|
| Core LLM | `generate(system, user, model, temp)` | Response generation |
| Core LLM | `batch_generate(requests)` | Parallel experiment execution |
| User Profile | `get_user_expertise_level()` | Adjust blend defaults |
| User Profile | `get_preferred_models()` | Select models for experiments |
| Credit Manager | `check_balance()` | Pre-experiment budget check |
| Credit Manager | `charge(credits, reason)` | Per-iteration billing |
| Prompt Store | `get_similar_prompts(embedding, k)` | Warm-start data transfer |
| Feedback System | `register_callback(session_id, callback)` | Real-time feedback |

---

## 6. Implementation Phases

### Phase 1: MVP (Weeks 1-3)
**Goal**: Basic learning loop with grid search, single task type

**Deliverables:**
```
- [ ] TuneHub base class interface (abstract)
- [ ] RePromptTuner implements on_event(), get_learned_model()
- [ ] Grid search over 5 personas (discretized to 0, 0.5, 1.0)
    → 3^5 = 243 combinations, but pruned by conflict constraints
    → Test 12 combinations per task type
- [ ] Simple task classifier (keyword-based only)
- [ ] User feedback UI: 1-5 star rating after each response
- [ ] Model storage: JSON file with blend + score
- [ ] Default blend: uniform weights for "general" task
```

**Success criteria:**
- Can learn a "coding_task" blend in ≤ 15 iterations
- User can see blend weights in settings
- Quality score trend increases monotonically (visualized)

**Credit target:** ≤ 2,000 per task

---

### Phase 2: Enhanced (Weeks 4-6)
**Goal**: Bayesian optimization, multi-task learning, better classification

**Deliverables:**
```
- [ ] Replace grid search with Gaussian Process + EI acquisition
- [ ] Implement Thompson sampling variant for exploration
- [ ] Multi-task GP: share length scales across related tasks
    → coding_task and building_task share kernel hyperparameters
- [ ] Upgrade task classifier: keyword + embedding ensemble
- [ ] Automated judge: Haiku-based quality evaluator
- [ ] Conflict/synergy matrix: user-adjustable in settings
- [ ] A/B testing framework: random 10% default-blend holdout
- [ ] Desktop 2 validation pipeline (offline)
```

**Success criteria:**
- Convergence in ≤ 10 iterations (down from 15)
- Fuzzy matching finds correct task 85% of time
- A/B test: learned blend beats default by ≥ 15% quality improvement

**Credit target:** ≤ 1,500 per task

---

### Phase 3: Polish (Weeks 7-8)
**Goal**: Production robustness, edge cases, performance

**Deliverables:**
```
- [ ] Warm-start from similar tasks: transfer learning
    → learned "coding_task" initializes "webdev_task" GP
- [ ] Online learning: update GP incrementally (no re-fit from scratch)
- [ ] Confidence calibration: is predicted quality actually achieved?
- [ ] Edge case: user contradicts themselves → detect inconsistency
- [ ] Edge case: all blends score poorly → detect impossible task
- [ ] Performance: GP optimization < 500ms (async)
- [ ] Privacy: observations anonymized, stored encrypted
- [ ] Export/Import: user can backup and restore their tunes
- [ ] Degradation detection: auto-trigger re-learning if scores drop
```

**Success criteria:**
- 99.9% uptime (no crashes during learning)
- GP optimization latency p95 < 500ms
- User can migrate tunes across devices

**Credit target:** ≤ 1,200 per task (transfer learning reduces iterations)

---

## 7. Validation Strategy

### 7.1 A/B Testing Framework

```
FUNCTION ab_test(tune, task_type, test_duration_days=7):
    
    # Randomly assign users to control or treatment
    user_bucket = hash(user_id + task_type) % 100
    
    IF user_bucket < 10:
        # 10% control: always use default blend
        group = "control"
        blend = DEFAULT_BLENDS[task_type]
    ELSE:
        # 90% treatment: use learned blend if available
        group = "treatment"
        blend = tune.best_blend IF tune ELSE DEFAULT_BLENDS[task_type]
    
    # Track metrics over test period
    metrics = {
        "avg_quality_score": rolling_mean(daily_scores),
        "user_satisfaction_rate": COUNT(score > 0.8) / COUNT(all),
        "repeat_usage_rate": user_returns_after_positive_experience,
        "credit_efficiency": quality_per_credit_spent
    }
    
    # Statistical validation after minimum sample size
    IF control.n > 30 AND treatment.n > 30:
        result = mann_whitney_u_test(treatment.scores, control.scores)
        
        IF result.p_value < 0.05 AND result.treatment_median > control.median * 1.15:
            RETURN "SIGNIFICANT_IMPROVEMENT"
        ELSE IF result.p_value < 0.05 AND result.treatment_median < control.median:
            RETURN "SIGNIFICANT_REGRESSION"
        ELSE:
            RETURN "NO_SIGNIFICANT_DIFFERENCE"
    
    RETURN "INSUFFICIENT_DATA"
```

### 7.2 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Quality score improvement | ≥ 15% over default | (learned_avg - default_avg) / default_avg |
| Convergence rate | ≥ 90% within 12 iterations | % of tasks reaching CONVERGED_* status |
| User satisfaction | ≥ 4.2 / 5.0 stars | Rolling 7-day average |
| False positive rate | ≤ 10% | Wrong task classification leading to bad blend |
| Credit efficiency | ≥ 0.001 quality/credit | quality_score / credits_consumed |
| Latency overhead | ≤ 500ms | Time from prompt to blend selection |

### 7.3 Tune Rejection Criteria

```
FUNCTION validate_tune_before_deployment(tune):
    
    rejections = []
    
    # Criterion 1: Insufficient data
    IF tune.observation_count < 5:
        rejections.append("INSUFFICIENT_OBSERVATIONS")
    
    # Criterion 2: Poor absolute quality
    IF tune.quality_score < 0.70:
        rejections.append("LOW_ABSOLUTE_QUALITY")
    
    # Criterion 3: High variance (unstable blend)
    IF tune.quality_std > 0.15:
        rejections.append("HIGH_VARIANCE")
    
    # Criterion 4: Failed A/B test
    ab_result = ab_test(tune, tune.task_id)
    IF ab_result == "SIGNIFICANT_REGRESSION":
        rejections.append("AB_TEST_REGRESSION")
    
    # Criterion 5: Validation on Desktop 2 failed
    desktop2_result = validate_on_desktop2(tune)
    IF desktop2_result == "REJECTED":
        rejections.append("VALIDATION_FAILED")
    
    # Criterion 6: User override frequency
    override_rate = get_user_override_rate(tune.task_id)
    IF override_rate > 0.30:
        rejections.append("HIGH_USER_OVERRIDE")
    
    IF rejections:
        RETURN {"status": "REJECTED", "reasons": rejections, "action": "RETRY_WITH_MORE_DATA"}
    ELSE:
        RETURN {"status": "APPROVED", "confidence": tune.quality_score}
```

### 7.4 Retry Strategy

```
FUNCTION handle_rejected_tune(tune, rejection_reasons):
    
    FOR reason IN rejection_reasons:
        
        IF reason == "INSUFFICIENT_OBSERVATIONS":
            # Run 3 more iterations
            extended_iterations = 3
            
        IF reason == "LOW_ABSOLUTE_QUALITY":
            # Check if default is also poor → task might be inherently hard
            default_score = evaluate_default_blend(tune.task_id)
            IF tune.quality_score > default_score * 1.05:
                RETURN "ACCEPT_RELATIVE_IMPROVEMENT"  # Accept if better than default
            ELSE:
                extended_iterations = 5  # Try more
                
        IF reason == "HIGH_VARIANCE":
            # Increase GP noise prior, re-fit with more data
            extended_iterations = 3
            gp_noise_prior = 0.2  # Up from 0.1
            
        IF reason == "AB_TEST_REGRESSION":
            # Disable tune, return to default, investigate
            flag_for_manual_review(tune)
            RETURN "DISABLE_AND_INVESTIGATE"
            
        IF reason == "VALIDATION_FAILED":
            # Desktop 2 suggests overfitting → add regularization
            gp_length_scale *= 1.5  # Smoother function
            extended_iterations = 4
            
        IF reason == "HIGH_USER_OVERRIDE":
            # Blend is technically good but user doesn't like style
            # Switch to preference learning (different objective)
            switch_to_preference_model(tune)
            RETURN "SWITCH_ALGORITHM"
    
    # Run extended learning
    FOR i IN RANGE(extended_iterations):
        learn_blend(tune.example_prompt, tune.task_id)
    
    RETURN re_validate(tune)
```

---

---

# SECTION 2: DICTATION TUNER

## 1. Algorithm Design

### 1.1 Chosen Algorithm: Context-Aware Active Learning with Confidence-Weighted Correction Map

**Why this algorithm fits:**
- Sparse, discrete corrections (word → word mappings)
- Domain-dependent behavior ("Kimi" means different things in crypto vs. AI contexts)
- User provides corrections on-the-fly (active learning scenario)
- Low-dimensional per-correction but high-dimensional context space
- Must handle concept drift (new terms emerge, old ones change meaning)

**Algorithm stack:**
1. **Base Corrector**: Trie-based prefix correction map with frequency weighting
2. **Context Classifier**: Small transformer (DistilBERT-level) for domain detection
3. **Selection Strategy**: Uncertainty sampling + diversity sampling hybrid
4. **Update Rule**: Exponential weighted moving average with recency bias
5. **Confidence Model**: Learned threshold for auto-apply vs. suggest

### 1.2 Pseudocode — Core Learning Loop

```
CLASS DictationTuner:
    
    INITIALIZE:
        # Core data structures
        correction_map = Trie()          # heard -> {should_be: count, contexts: []}
        context_classifier = DistilBERTClassifier(num_domains=8)
        confidence_model = ConfidenceThresholdLearner()
        
        # Domain definitions
        domains = [
            "general", "software", "crypto", "medical", 
            "legal", "creative_writing", "business", "custom"
        ]
        
        # Active learning state
        uncertainty_queue = PriorityQueue()  # (uncertainty_score, heard_text, context)
        
    FUNCTION process_transcription(heard_text, audio_features, user_context):
        """
        Main entry: called after every transcription
        """
        
        # Step 1: Detect domain from context
        domain, domain_confidence = context_classifier.classify(
            user_context.recent_prompts,
            user_context.active_app,
            user_context.time_of_day
        )
        
        # Step 2: Apply corrections at token/word level
        tokens = tokenize(hear_text)
        corrected_tokens = []
        applied_corrections = []
        
        FOR token IN tokens:
            # Check exact match in correction map
            IF token IN correction_map:
                candidates = correction_map[token]  # {correction: metadata}
                
                # Score each candidate for this domain
                best_candidate = None
                best_score = 0
                
                FOR correction, meta IN candidates:
                    domain_score = meta.domain_distribution[domain]
                    frequency_score = meta.frequency / meta.total_uses
                    recency_score = exp(-0.1 * days_since(meta.last_used))
                    
                    score = 0.4 * domain_score + 0.4 * frequency_score + 0.2 * recency_score
                    
                    IF score > best_score AND score > confidence_model.threshold(domain):
                        best_score = score
                        best_candidate = correction
                
                IF best_candidate:
                    corrected_tokens.append(best_candidate)
                    applied_corrections.append({
                        "heard": token,
                        "applied": best_candidate,
                        "confidence": best_score,
                        "auto_applied": True
                    })
                ELSE:
                    corrected_tokens.append(token)
            ELSE:
                corrected_tokens.append(token)
        
        corrected_text = detokenize(corrected_tokens)
        
        # Step 3: Identify uncertain tokens for active learning
        uncertain_tokens = detect_uncertainty(
            heard_text, audio_features, corrected_text, correction_map
        )
        
        # Queue for potential user verification
        FOR utoken IN uncertain_tokens:
            uncertainty_queue.push({
                "priority": utoken.uncertainty,
                "heard": utoken.text,
                "suggested": utoken.best_guess,
                "context": domain,
                "audio_snippet_ref": utoken.audio_ref
            })
        
        RETURN {
            "corrected_text": corrected_text,
            "applied_corrections": applied_corrections,
            "uncertain_tokens": uncertain_tokens,
            "domain": domain
        }
    
    FUNCTION record_user_correction(heard_text, corrected_text, context_domain):
        """
        Called when user edits the transcription
        """
        
        # Step 1: Align heard and corrected to find word-level differences
        alignment = needleman_wunsch_align(
            tokenize(heard_text.lower()),
            tokenize(corrected_text.lower())
        )
        
        # Step 2: Extract corrections from alignment
        corrections = []
        FOR op, heard_word, corrected_word IN alignment:
            IF op == "SUBSTITUTE" OR op == "INSERT":
                corrections.append({
                    "heard": heard_word,
                    "should_be": corrected_word,
                    "operation": op
                })
        
        # Step 3: Update correction map with recency-weighting
        FOR corr IN corrections:
            entry = correction_map.get_or_create(corr.heard)
            
            IF corr.should_be NOT IN entry:
                entry[corr.should_be] = {
                    "frequency": 0,
                    "first_seen": now(),
                    "domain_distribution": {d: 0 FOR d IN domains},
                    "context_examples": []
                }
            
            target = entry[corr.should_be]
            
            # Update frequency with EWMA (α=0.7 favors recent)
            target.frequency = 0.7 * target.frequency + 0.3 * 1.0
            target.total_uses = (target.total_uses OR 0) + 1
            target.last_used = now()
            
            # Update domain distribution
            target.domain_distribution[context_domain] += 1
            
            # Store context example (limited to last 5)
            target.context_examples.append({
                "full_sentence": corrected_text,
                "timestamp": now()
            })
            IF LENGTH(target.context_examples) > 5:
                POP_FIRST(target.context_examples)
            
            # Normalize domain distribution
            total = SUM(target.domain_distribution)
            FOR d IN domains:
                target.domain_distribution[d] /= total
        
        # Step 4: Update confidence model
        confidence_model.update(
            correction=corrections[0],  # Primary correction
            domain=context_domain,
            user_accepted=True
        )
        
        # Step 5: Prune low-confidence entries
        prune_stale_entries(correction_map, max_age_days=90, min_frequency=2)
        
        RETURN {"corrections_recorded": LENGTH(corrections)}
    
    FUNCTION detect_uncertainty(heard_text, audio_features, corrected_text, correction_map):
        """
        Identify tokens where we're unsure about the correction
        """
        uncertain = []
        tokens = tokenize(heard_text)
        
        FOR token IN tokens:
            # Signal 1: Token is in correction map but with low confidence
            IF token IN correction_map:
                candidates = correction_map[token]
                max_confidence = MAX(meta.frequency FOR meta IN candidates.values())
                IF max_confidence < 0.6:
                    uncertain.append({
                        "text": token,
                        "uncertainty": 1.0 - max_confidence,
                        "best_guess": ARGMAX(candidates, key=lambda c: c.frequency),
                        "reason": "low_correction_confidence"
                    })
            
            # Signal 2: Audio features indicate poor recognition
            audio_confidence = audio_features.get_token_confidence(token)
            IF audio_confidence < 0.7:
                uncertain.append({
                    "text": token,
                    "uncertainty": 1.0 - audio_confidence,
                    "best_guess": token,
                    "reason": "low_audio_confidence"
                })
            
            # Signal 3: Token looks like a proper noun (capitalized, rare)
            IF is_proper_noun(token) AND token NOT IN correction_map:
                uncertain.append({
                    "text": token,
                    "uncertainty": 0.8,
                    "best_guess": token,
                    "reason": "unseen_proper_noun"
                })
            
            # Signal 4: Phonetic similarity to known correction
            phonetic_matches = fuzzy_phonetic_match(token, correction_map.keys(), threshold=0.7)
            IF phonetic_matches:
                uncertain.append({
                    "text": token,
                    "uncertainty": 0.6,
                    "best_guess": phonetic_matches[0],
                    "reason": "phonetic_ambiguity"
                })
        
        RETURN uncertain
```

### 1.3 Convergence Criteria

```
CONVERGENCE_CHECK(correction_map, domain):
    
    # Criterion 1: Sufficient corrections in domain
    domain_corrections = COUNT(
        entry FOR entry IN correction_map 
        WHERE entry.domain_distribution[domain] > 0.5
    )
    IF domain_corrections < 10:
        RETURN "INSUFFICIENT_DATA"
    
    # Criterion 2: Correction confidence stabilized
    recent_corrections = FILTER correction_map WHERE days_since(last_used) < 7
    avg_confidence = MEAN(MAX(entry.frequency) FOR entry IN recent_corrections)
    IF avg_confidence > 0.85 AND STD(recent_corrections.confidence) < 0.1:
        RETURN "CONVERGED_STABLE"
    
    # Criterion 3: Auto-apply rate acceptable
    auto_apply_rate = COUNT(auto_applied) / COUNT(all_corrections)
    IF auto_apply_rate > 0.80 AND user_override_rate < 0.10:
        RETURN "CONVERGED_AUTO_APPLY"
    
    # Criterion 4: User override rate too high (divergence)
    IF user_override_rate > 0.40:
        RETURN "DIVERGING_REVIEW_NEEDED"
    
    RETURN "LEARNING"
```

---

## 2. Experimentation Protocol

### 2.1 Iteration Structure

Dictation learning is **event-driven** (not batch iterations). Each user interaction is an "iteration."

| Phase | Trigger | What Happens | Data Goal |
|-------|---------|--------------|-----------|
| Bootstrap | First use in domain | Collect 10 corrections manually | Seed correction map |
| Active | Every transcription | Auto-apply + suggest uncertain | Expand map |
| Review | Daily/weekly | Present top uncertain corrections | User confirms/rejects |
| Consolidation | 30+ corrections in domain | Prune, re-weight, validate | Optimize map |

### 2.2 Per-Interaction Detail

```
INTERACTION_LOOP(audio_input, user_context):
    
    # Step 1: Transcribe (external: Groq Whisper)
    transcription = groq_whisper.transcribe(audio_input)
    heard_text = transcription.text
    audio_features = transcription.confidence_per_token
    
    # Step 2: Domain detection
    domain, domain_conf = context_classifier.classify(
        recent_history=user_context.last_5_prompts,
        active_application=user_context.foreground_app,
        document_context=user_context.current_document_preview
    )
    
    # Step 3: Apply known corrections
    result = process_transcription(heard_text, audio_features, {
        "domain": domain,
        "recent_prompts": user_context.last_5_prompts
    })
    
    # Step 4: Present to user
    IF LENGTH(result.applied_corrections) > 0:
        # Show "Auto-corrected X → Y" toast (non-intrusive)
        show_correction_toast(result.applied_corrections)
    
    IF LENGTH(result.uncertain_tokens) > 0:
        # Highlight uncertain words, allow quick click-to-correct
        highlight_uncertain_tokens(result.uncertain_tokens)
    
    # Step 5: Wait for user action (async)
    user_action = await_user_action(timeout=30000)
    
    IF user_action.type == "CORRECTION":
        # User edited the text
        record_user_correction(
            heard_text=heard_text,
            corrected_text=user_action.final_text,
            context_domain=domain
        )
        
    IF user_action.type == "ACCEPT":
        # User accepted transcription (implicit confirmation)
        IF result.applied_corrections:
            FOR acorr IN result.applied_corrections:
                confidence_model.update_positive(acorr)
    
    IF user_action.type == "REJECT_AUTO_CORRECTION":
        # User undid an auto-correction
        FOR acorr IN user_action.rejected_corrections:
            # Penalize this correction
            confidence_model.update_negative(acorr)
            # Flag for review
            flag_correction_for_review(acorr)
    
    # Step 6: Periodic active learning prompt
    IF should_prompt_for_review(domain):
        top_uncertain = uncertainty_queue.peek(k=3)
        show_review_dialog(top_uncertain)
    
    RETURN result.corrected_text
```

### 2.3 Quality Measurement

```
FUNCTION measure_quality(domain, window="7d"):
    
    events = get_events(domain, window)
    
    metrics = {
        # Correction accuracy
        "auto_apply_correct": COUNT(e WHERE e.auto_applied AND e.user_accepted),
        "auto_apply_wrong": COUNT(e WHERE e.auto_applied AND e.user_rejected),
        "auto_apply_accuracy": auto_apply_correct / (auto_apply_correct + auto_apply_wrong),
        
        # User effort reduction
        "avg_corrections_before": baseline_manual_corrections_per_session,
        "avg_corrections_after": COUNT(e.user_corrections) / COUNT(sessions),
        "effort_reduction": (avg_corrections_before - avg_corrections_after) / avg_corrections_before,
        
        # Coverage
        "unique_words_seen": COUNT(DISTINCT heard_tokens),
        "unique_words_corrected": COUNT(DISTINCT entries IN correction_map),
        "coverage": unique_words_corrected / unique_words_seen,
        
        # Confidence calibration
        "predicted_auto_apply_rate": MEAN(e.confidence FOR e IN events WHERE e.auto_applied),
        "actual_auto_apply_accuracy": auto_apply_accuracy,
        "calibration_error": ABS(predicted_auto_apply_rate - actual_auto_apply_accuracy)
    }
    
    RETURN metrics
```

### 2.4 Credit Consumption Model

| Component | Calls/Unit | Credits/Call | Unit Cost | Notes |
|-----------|-----------|--------------|-----------|-------|
| Groq Whisper transcription | 1 | ~15 | 15 | Per audio minute |
| Context classification (DistilBERT) | 1 | ~2 | 2 | Per transcription |
| Confidence model update | 1 | ~0.5 | 0.5 | Per correction |
| Active learning review dialog | 1 | ~5 | 5 | Per prompt (3x/week) |
| **Bootstrap (10 corrections)** | | | **~225** | Initial learning |
| **Per-session (avg 5 min audio)** | | | **~80** | Ongoing |

**Total to reach convergence**: ~1,200 credits
- Bootstrap: 10 corrections × 22.5 = 225
- Active learning (40 sessions): 40 × 25 = 1,000
- Review consolidation: 3 sessions × 50 = 150
- **Total: ~1,375** (target ≤ 1,200 via optimization)

---

## 3. Data Collection & Feature Engineering

### 3.1 Raw Data Collected

```json
{
  "event_id": "dict_2024_0515_001",
  "timestamp": "2024-05-15T10:23:15Z",
  "session_id": "sess_voice_abc",
  
  "audio": {
    "duration_sec": 45.2,
    "sample_rate": 16000,
    "groq_confidence": 0.89,
    "confidence_per_token": [0.92, 0.88, 0.95, 0.71, 0.93],
    "language_detected": "en",
    "audio_fingerprint": "afp_sha256_abc123"
  },
  
  "transcription": {
    "heard_text": "Set up a meeting with Kimi K2 for the blockchain discussion",
    "corrected_text": "Set up a meeting with Kimi K2 for the blockchain discussion",
    "corrections_applied": [
      {
        "heard": "kimi",
        "applied": "Kimi K2",
        "confidence": 0.94,
        "auto_applied": true,
        "domain": "software"
      },
      {
        "heard": "block chain",
        "applied": "blockchain",
        "confidence": 0.88,
        "auto_applied": true,
        "domain": "software"
      }
    ]
  },
  
  "context": {
    "detected_domain": "software",
    "domain_confidence": 0.87,
    "active_application": "Slack",
    "document_preview": "Project roadmap...",
    "recent_prompts": ["Review the smart contract", "Deploy to testnet"],
    "time_of_day": "morning",
    "user_id": "user_42"
  },
  
  "user_action": {
    "action_type": "ACCEPT",
    "latency_ms": 0,
    "final_text": "Set up a meeting with Kimi K2 for the blockchain discussion",
    "manual_edits": [],
    "rejected_corrections": []
  }
}
```

### 3.2 Feature Engineering Pipeline

```
FEATURE_EXTRACT(audio, heard_text, context):
    
    # Audio features
    audio_features = {
        "avg_confidence": MEAN(audio.confidence_per_token),
        "min_confidence": MIN(audio.confidence_per_token),
        "confidence_variance": VAR(audio.confidence_per_token),
        "duration_sec": audio.duration_sec,
        "words_per_second": len(tokenize(heard_text)) / audio.duration_sec,
        "has_pauses": detect_pauses(audio.waveform),
        "background_noise_level": estimate_noise(audio.spectrum)
    }
    
    # Text features (per token)
    token_features = []
    FOR token IN tokenize(heard_text):
        features = {
            "token": token,
            "is_proper_noun": is_proper_noun(token),
            "is_technical_term": token IN technical_dictionary,
            "is_acronym": regex_match(token, "^[A-Z]{2,}$"),
            "phonetic_code": double_metaphone(token),
            "char_length": len(token),
            "syllable_count": count_syllables(token),
            "frequency_in_corpus": word_frequency(token)
        }
        token_features.append(features)
    
    # Context features
    context_features = {
        "domain": context.detected_domain,
        "domain_confidence": context.domain_confidence,
        "active_app_category": categorize_app(context.active_application),
        "time_bucket": bucket_time(context.time_of_day),
        "prompt_similarity_to_history": max_similarity(
            embed(heard_text),
            [embed(p) FOR p IN context.recent_prompts]
        ),
        "document_domain_signal": extract_domain_from_text(context.document_preview)
    }
    
    RETURN {audio_features, token_features, context_features}
```

### 3.3 Domain Classification Approach

```
CLASS ContextDomainClassifier:
    
    # Multi-signal ensemble classifier
    
    INITIALIZE:
        # Pre-trained on domain-labeled text snippets
        text_encoder = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim
        app_domain_map = load_app_categories()  # {"Photoshop": "creative", ...}
        
        # Domain centroids from training data
        domain_centroids = {
            "software": [0.12, -0.34, ..., 0.89],
            "crypto": [0.45, 0.12, ..., -0.23],
            ...
        }
    
    FUNCTION classify(recent_prompts, active_app, document_preview):
        
        # Signal 1: Text content (recent prompts + document)
        text_input = " ".join(recent_prompts) + " " + document_preview
        text_emb = text_encoder.encode(text_input)
        
        text_scores = {}
        FOR domain, centroid IN domain_centroids:
            text_scores[domain] = cosine_similarity(text_emb, centroid)
        
        # Signal 2: Active application
        app_scores = {d: 0 FOR d IN domains}
        IF active_app IN app_domain_map:
            app_domain = app_domain_map[active_app]
            app_scores[app_domain] = 1.0
        
        # Signal 3: Time patterns (weak signal)
        time_scores = {d: 0 FOR d IN domains}
        hour = datetime.now().hour
        IF 9 <= hour <= 17:
            time_scores["business"] += 0.3
            time_scores["software"] += 0.2
        IF hour >= 20 OR hour <= 6:
            time_scores["creative_writing"] += 0.2
        
        # Ensemble (weighted average)
        final_scores = {}
        FOR domain IN domains:
            final_scores[domain] = (
                0.6 * text_scores[domain] +
                0.3 * app_scores[domain] +
                0.1 * time_scores[domain]
            )
        
        best_domain = ARGMAX(final_scores)
        confidence = softmax(final_scores)[best_domain]
        
        RETURN (best_domain, confidence)
```

---

## 4. Model Storage & Retrieval

### 4.1 Learned Model Schema

```json
{
  "model_version": "dictation_v2.0",
  "created_at": "2024-05-01T00:00:00Z",
  "last_updated": "2024-05-20T16:45:00Z",
  
  "global_settings": {
    "auto_apply_threshold": 0.85,
    "suggestion_threshold": 0.60,
    "max_corrections_per_sentence": 5,
    "prune_after_days": 90,
    "min_frequency_for_auto_apply": 3
  },
  
  "correction_map": {
    "kimi": {
      "Kimi K2": {
        "frequency": 4.2,
        "total_uses": 12,
        "first_seen": "2024-05-02T09:00:00Z",
        "last_used": "2024-05-20T14:30:00Z",
        "domain_distribution": {
          "software": 0.75,
          "general": 0.17,
          "crypto": 0.08
        },
        "context_examples": [
          "Ask Kimi K2 to review the code",
          "Kimi K2 suggested using async",
          "Compare with Kimi K2 output"
        ],
        "user_acceptance_rate": 0.92,
        "phonetic_variants": ["kimi", "kimmy", "key me"]
      },
      "Kimmy": {
        "frequency": 0.3,
        "total_uses": 1,
        "domain_distribution": {"general": 1.0},
        "context_examples": ["My friend Kimmy is coming"],
        "user_acceptance_rate": 1.0
      }
    },
    "block chain": {
      "blockchain": {
        "frequency": 3.8,
        "total_uses": 8,
        "domain_distribution": {
          "crypto": 0.80,
          "software": 0.20
        },
        "user_acceptance_rate": 0.95
      }
    }
  },
  
  "domain_profiles": {
    "software": {
      "correction_count": 47,
      "convergence_status": "CONVERGED_AUTO_APPLY",
      "avg_confidence": 0.89,
      "auto_apply_rate": 0.84,
      "user_override_rate": 0.06
    },
    "crypto": {
      "correction_count": 23,
      "convergence_status": "LEARNING",
      "avg_confidence": 0.76,
      "auto_apply_rate": 0.62,
      "user_override_rate": 0.15
    }
  },
  
  "confidence_model": {
    "thresholds_per_domain": {
      "software": 0.82,
      "crypto": 0.75,
      "general": 0.90,
      "medical": 0.95
    },
    "calibration_curve": {
      "bins": [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
      "predicted": [0.55, 0.65, 0.75, 0.85, 0.92, 0.98],
      "actual": [0.52, 0.63, 0.78, 0.87, 0.94, 0.99]
    }
  },
  
  "meta": {
    "total_corrections_learned": 142,
    "total_user_sessions": 89,
    "total_audio_minutes": 445,
    "credit_consumed": 1180,
    "most_active_domain": "software"
  }
}
```

### 4.2 Retrieval & Matching Logic

```
FUNCTION lookup_correction(heard_word, current_domain, context):
    
    heard_lower = heard_word.lower()
    
    # Step 1: Exact match
    IF heard_lower IN correction_map:
        candidates = correction_map[heard_lower]
        
        # Score candidates by domain match
        scored = []
        FOR correction, meta IN candidates:
            domain_score = meta.domain_distribution.get(current_domain, 0.05)
            recency = exp(-0.1 * days_since(meta.last_used))
            freq = min(meta.frequency / 5.0, 1.0)  # Cap at 5 uses
            
            score = 0.5 * domain_score + 0.3 * recency + 0.2 * freq
            
            # Penalize if user recently rejected this correction
            IF was_recently_rejected(heard_lower, correction):
                score *= 0.1
            
            scored.append((correction, score, meta))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]
        
        # Decide action based on confidence
        IF best[1] > global_settings.auto_apply_threshold:
            RETURN {"action": "AUTO_APPLY", "correction": best[0], "confidence": best[1]}
        ELSE IF best[1] > global_settings.suggestion_threshold:
            RETURN {"action": "SUGGEST", "correction": best[0], "confidence": best[1]}
        ELSE:
            RETURN {"action": "PASS", "heard": heard_word}
    
    # Step 2: Fuzzy match (phonetic + edit distance)
    phonetic_matches = fuzzy_phonetic_match(heard_lower, correction_map.keys(), threshold=0.8)
    IF phonetic_matches:
        best_match = phonetic_matches[0]
        candidates = correction_map[best_match]
        
        # Recalculate with penalty for fuzzy match
        scored = []
        FOR correction, meta IN candidates:
            base_score = meta.domain_distribution.get(current_domain, 0.05)
            fuzzy_penalty = 0.8  # Reduce confidence for fuzzy match
            score = base_score * fuzzy_penalty
            scored.append((correction, score, meta))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]
        
        IF best[1] > global_settings.suggestion_threshold:
            RETURN {"action": "SUGGEST", "correction": best[0], "confidence": best[1], "note": "fuzzy_match"}
    
    # Step 3: No match found
    RETURN {"action": "PASS", "heard": heard_word}
```

### 4.3 Confidence Thresholds

| Correction Confidence | Action | UI Behavior |
|----------------------|--------|-------------|
| ≥ 0.90 | Auto-apply silently | Word replaced, brief underline |
| 0.75 - 0.89 | Auto-apply with toast | "Corrected X → Y" shown 2 seconds |
| 0.60 - 0.74 | Suggest inline | Red dotted underline, hover to accept |
| 0.40 - 0.59 | Suggest in review panel | Add to "Possible corrections" list |
| < 0.40 | Ignore | No action |

### 4.4 Fallback Behavior

```
FUNCTION fallback_correction(heard_text, domain):
    
    # No learned corrections available for this domain
    IF is_new_domain(domain):
        RETURN {
            "corrected_text": heard_text,
            "action": "NO_CORRECTIONS",
            "message": "Learning your speech patterns in this domain...",
            "trigger_bootstrap": True
        }
    
    # Domain has corrections but none match
    IF has_domain_corrections(domain) BUT no_matches:
        # Try general domain as fallback
        general_result = lookup_in_domain(heard_text, "general")
        IF general_result.action != "PASS":
            general_result.fallback_from = domain
            general_result.note = "fell_back_to_general"
            RETURN general_result
    
    # Truly unknown word
    IF is_proper_noun_or_technical(heard_text):
        # Flag for quick user confirmation
        RETURN {
            "corrected_text": heard_text,
            "action": "FLAG_UNCERTAIN",
            "suggestions": [capitalized(heard_text), heard_text],
            "message": f"Did you mean '{capitalized(heard_text)}'?"
        }
    
    RETURN {"corrected_text": heard_text, "action": "PASS"}
```

---

## 5. Integration Points

### 5.1 TuneHub Base Class Interface

```python
class DictationTuner(TuneHubBase):
    """
    Event-driven tuner for real-time transcription correction.
    """
    
    def __init__(self, hub_config):
        super().__init__(hub_config)
        self.correction_map = CorrectionMap()
        self.domain_classifier = ContextDomainClassifier()
        self.confidence_model = ConfidenceThresholdLearner()
        self.uncertainty_queue = PriorityQueue()
        
    def register_with_hub(self, hub):
        hub.register_tuner(
            name="dictation",
            trigger_events=["TRANSCRIPTION_COMPLETE", "USER_TEXT_EDIT", "REVIEW_REQUEST"],
            output_format="corrected_text",
            priority=2
        )
    
    def on_event(self, event_type, payload):
        
        IF event_type == "TRANSCRIPTION_COMPLETE":
            # Main processing path
            result = self.process_transcription(
                heard_text=payload.text,
                audio_features=payload.audio_metadata,
                user_context=payload.context
            )
            RETURN CorrectionEvent(
                corrected_text=result.corrected_text,
                corrections=result.applied_corrections,
                uncertain=result.uncertain_tokens,
                domain=result.domain
            )
        
        IF event_type == "USER_TEXT_EDIT":
            # User manually corrected transcription
            diff = compute_diff(payload.original_text, payload.edited_text)
            self.record_user_correction(
                heard_text=payload.original_text,
                corrected_text=payload.edited_text,
                context_domain=payload.detected_domain
            )
            # Feed diff back for immediate model update
            self.update_model_incremental(diff)
        
        IF event_type == "REVIEW_REQUEST":
            # User clicked "Review my corrections"
            top_uncertain = self.uncertainty_queue.peek(k=10)
            RETURN ReviewDialogEvent(items=top_uncertain)
    
    def get_learned_model(self):
        RETURN {
            "correction_map": self.correction_map.serialize(),
            "domain_profiles": self.domain_classifier.get_profiles(),
            "confidence_model": self.confidence_model.serialize(),
            "global_settings": self.settings
        }
```

### 5.2 Desktop 1 vs Desktop 2 Responsibilities

| Responsibility | Desktop 1 (Main) | Desktop 2 (Isolated) |
|---------------|------------------|---------------------|
| Real-time transcription | Primary (Groq Whisper API) | Backup provider |
| Correction application | Live in text fields | N/A |
| Model updates | Immediate (per correction) | Batch validation |
| Audio storage | Ephemeral (5 min TTL) | None |
| User feedback UI | Full modal + toast | N/A |
| Model training/optimization | Lightweight incremental | Heavy re-training |
| Privacy-sensitive audio | Never leaves Desktop 1 | N/A |

```
# Desktop 2 batch validation (weekly)
FUNCTION weekly_validation_on_desktop2():
    # Pull week's correction data from Desktop 1 (anonymized)
    weekly_data = desktop1.export_anonymized_corrections()
    
    # Validate: simulate corrections with held-out test set
    test_set = weekly_data.sample(20%)
    
    # Run correction engine on test set
    predictions = []
    FOR item IN test_set:
        pred = correction_engine.process(item.heard, item.context)
        predictions.append(pred)
    
    # Metrics
    accuracy = COUNT(pred.corrected == item.user_corrected) / COUNT(test_set)
    false_positive = COUNT(pred.auto_applied AND pred.corrected != item.user_corrected)
    
    IF accuracy < 0.80 OR false_positive > 0.05:
        # Trigger model adjustment on Desktop 1
        desktop1.push_adjustment({
            "action": "RAISE_THRESHOLDS",
            "domains_affected": ["all"],
            "amount": 0.05
        })
```

### 5.3 APIs Needed

| Feature | API | Purpose |
|---------|-----|---------|
| Speech Engine | `transcribe(audio_blob)` | Raw transcription |
| Speech Engine | `transcribe_with_confidence(audio_blob)` | Per-token confidence |
| Core NLP | `embed(text)` | Domain classification |
| User Profile | `get_domain_preferences()` | User-defined domains |
| User Profile | `get_correction_history()` | Past corrections for warm-start |
| Credit Manager | `charge(credits, "dictation")` | Per-transcription billing |
| Settings | `register_settings_panel(tuner_name, schema)` | Correction threshold UI |
| UI Framework | `show_toast(message, duration)` | Non-intrusive feedback |
| UI Framework | `highlight_text(range, style)` | Mark uncertain words |

---

## 6. Implementation Phases

### Phase 1: MVP (Weeks 1-3)
**Goal**: Basic correction map with manual entry, single domain

```
- [ ] TuneHub interface implementation
- [ ] Correction map: key-value store (heard -> corrected)
- [ ] Simple auto-apply: exact match only, no context
- [ ] User feedback: click-to-correct UI in transcription panel
- [ ] Domain: single "general" domain
- [ ] Storage: JSON file
- [ ] Bootstrap: manual entry of 10 common corrections in settings
```

**Success criteria:**
- User can manually add "heard → corrected" pairs
- System auto-applies exact matches with > 90% accuracy
- User sees list of applied corrections

**Credit target:** ≤ 300 (bootstrapping only)

---

### Phase 2: Enhanced (Weeks 4-6)
**Goal**: Context-aware corrections, active learning, domain detection

```
- [ ] Context domain classifier (keyword + app signal)
- [ ] Domain-specific correction maps
- [ ] Confidence model with learned thresholds per domain
- [ ] Active learning: detect uncertain tokens, prompt user
- [ ] Fuzzy matching: phonetic + edit distance for near-misses
- [ ] User override tracking: penalize rejected corrections
- [ ] Recency weighting: EWMA update rule
- [ ] Review panel: weekly "Review corrections" prompt
```

**Success criteria:**
- Auto-apply rate ≥ 60% with ≤ 10% user rejection
- Domain detection accuracy ≥ 80%
- Active learning: user corrects ≤ 30% fewer words than baseline

**Credit target:** ≤ 1,200 (full learning loop)

---

### Phase 3: Polish (Weeks 7-8)
**Goal**: Robustness, personalization, edge cases

```
- [ ] Phonetic encoding: Double Metaphone for sound-alikes
- [ ] Multi-word corrections: "block chain" → "blockchain"
- [ ] Abbreviation expansion: "JS" → "JavaScript" in software context
- [ ] Personal vocabulary: learn user's specific jargon
- [ ] Concept drift detection: auto-prune outdated corrections
- [ ] Import/Export: share correction profiles across devices
- [ ] Privacy mode: local-only processing, no cloud storage
- [ ] Performance: < 50ms correction lookup latency
```

**Success criteria:**
- Lookup latency p99 < 50ms
- Multi-word correction accuracy ≥ 85%
- User override rate < 5% after 2 weeks of use

**Credit target:** ≤ 800 (optimization reduces API calls)

---

## 7. Validation Strategy

### 7.1 A/B Testing

```
FUNCTION ab_test_dictation(user_segment, duration_days=14):
    
    # Segment: 50% control (no auto-corrections), 50% treatment
    
    control_metrics = {
        "manual_corrections_per_minute": measure_for_group("control"),
        "user_satisfaction": survey("control")
    }
    
    treatment_metrics = {
        "manual_corrections_per_minute": measure_for_group("treatment"),
        "auto_apply_rate": measure_for_group("treatment", "auto_applied"),
        "user_satisfaction": survey("treatment"),
        "correction_acceptance_rate": measure_for_group("treatment", "accepted")
    }
    
    # Primary metric: manual corrections reduced
    reduction = (control.manual_corr - treatment.manual_corr) / control.manual_corr
    
    # Secondary: satisfaction not harmed
    satisfaction_delta = treatment.satisfaction - control.satisfaction
    
    IF reduction > 0.40 AND satisfaction_delta > -0.2:
        RETURN "SIGNIFICANT_IMPROVEMENT"
    ELSE IF satisfaction_delta < -0.3:
        RETURN "USER_SATISFACTION_REGRESSION"
    ELSE:
        RETURN "INCONCLUSIVE"
```

### 7.2 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Word Error Rate (WER) reduction | ≥ 30% | (WER_default - WER_tuned) / WER_default |
| Auto-apply accuracy | ≥ 90% | Correct auto-applications / Total auto-applications |
| User override rate | ≤ 10% | Overrides / Auto-applications |
| Active learning coverage | ≥ 70% | Known words / Frequently spoken words |
| Correction latency | ≤ 50ms | Time from transcription to corrected output |
| Domain classification accuracy | ≥ 80% | Correct domain / All transcriptions |

### 7.3 Tune Rejection Criteria

```
FUNCTION validate_dictation_tune(tune):
    
    rejections = []
    
    # Criterion 1: Too many false positives
    IF tune.false_positive_rate > 0.15:
        rejections.append("HIGH_FALSE_POSITIVE")
    
    # Criterion 2: User override rate too high
    IF tune.user_override_rate > 0.25:
        rejections.append("HIGH_OVERRIDE")
    
    # Criterion 3: Domain confusion
    IF tune.domain_misclassification_rate > 0.30:
        rejections.append("DOMAIN_CONFUSION")
    
    # Criterion 4: Insufficient coverage
    IF tune.coverage < 0.30:
        rejections.append("LOW_COVERAGE")
    
    # Criterion 5: A/B test failure
    ab_result = ab_test_dictation(tune)
    IF ab_result == "USER_SATISFACTION_REGRESSION":
        rejections.append("SATISFACTION_REGRESSION")
    
    IF rejections:
        RETURN {"status": "REJECTED", "reasons": rejections}
    ELSE:
        RETURN {"status": "APPROVED"}
```

### 7.4 Retry Strategy

```
FUNCTION handle_rejected_dictation(tune, reasons):
    
    FOR reason IN reasons:
        
        IF reason == "HIGH_FALSE_POSITIVE":
            # Raise all thresholds by 0.1
            tune.global_settings.auto_apply_threshold += 0.10
            # Re-weight: require more confirmations
            FOR entry IN tune.correction_map:
                entry.frequency *= 0.7  # Reduce confidence
        
        IF reason == "HIGH_OVERRIDE":
            # Disable auto-apply for contested corrections
            contested = FILTER entry WHERE entry.override_rate > 0.3
            FOR entry IN contested:
                entry.auto_apply_disabled = True
                entry.action = "SUGGEST_ONLY"
        
        IF reason == "DOMAIN_CONFUSION":
            # Strengthen domain classifier with more context
            tune.domain_classifier.context_window += 3  # More prompts
            tune.domain_classifier.app_weight += 0.1
        
        IF reason == "LOW_COVERAGE":
            # Reduce minimum frequency threshold
            tune.global_settings.min_frequency_for_auto_apply -= 1
            # Extend bootstrap period
            tune.bootstrap_target += 5
    
    RETURN re_validate(tune)
```

---

---

# SECTION 3: AGENT TUNER

## 1. Algorithm Design

### 1.1 Chosen Algorithm: Causal Reinforcement Learning with Program Synthesis (CRL-PS)

**Why this algorithm fits:**
- Agent tuning involves sequences of actions with delayed rewards
- Must learn causal relationships (action X → outcome Y, not just correlations)
- Recipes must be generalizable and reusable (program synthesis)
- Environment is partially observable (Desktop 2 is black-box at start)
- Safety constraint: actions on Desktop 2 must not harm Desktop 1

**Algorithm stack:**
1. **Exploration**: Hierarchical task planner with macro-action library
2. **Causal Model**: Structural Causal Model (SCM) with do-calculus for intervention reasoning
3. **Policy Learning**: Proximal Policy Optimization (PPO) with safety constraints
4. **Program Synthesis**: Domain-specific language (DSL) for action sequences → reusable recipes
5. **Validation**: Counterfactual simulation on Desktop 2 before deployment

### 1.2 Pseudocode — Core Learning Loop

```
CLASS AgentTuner:
    
    INITIALIZE:
        # Action space definition
        macro_actions = load_macro_library()  # 50+ predefined macros
        dsl = AgentRecipeDSL()  # Domain-specific language for recipes
        
        # Causal model
        scm = StructuralCausalModel(
            variables=["click", "input", "scroll", "wait", "menu_open", "dialog_state", "target_state"],
            edges=[]  # Learned dynamically
        )
        
        # Policy network (lightweight: action sequences are short)
        policy = PPO_Policy(
            state_dim=128,
            action_dim=len(macro_actions),
            hidden_dims=[64, 64],
            learning_rate=3e-4
        )
        
        # Recipe store
        recipe_library = RecipeLibrary()
        
        # Desktop 2 interface
        env = Desktop2Environment(headless=True, snapshot_capable=True)
    
    FUNCTION learn_recipe(task_description, target_app, success_criteria):
        """
        Main entry: learn a reusable recipe for a task
        """
        
        # Step 1: Decompose task into sub-goals
        subgoals = decompose_task(task_description)
        
        # Step 2: Retrieve similar recipes for warm-start
        similar_recipes = recipe_library.retrieve_similar(
            task_embedding=embed(task_description),
            target_app=target_app,
            k=3
        )
        
        # Step 3: Initialize policy from similar recipes (transfer learning)
        IF similar_recipes:
            policy.initialize_from_recipes(similar_recipes)
            scm.merge_causal_graphs([r.causal_graph FOR r IN similar_recipes])
        
        # Step 4: Exploration-Exploitation Loop
        episode_results = []
        
        FOR episode IN 1..MAX_EPISODES:
            
            # Snapshot Desktop 2 for reset
            env.save_snapshot("pre_episode")
            
            # Run episode
            trajectory = run_episode(
                env=env,
                policy=policy,
                subgoals=subgoals,
                max_steps=50,
                target_app=target_app
            )
            
            # Evaluate outcome
            reward = evaluate_trajectory(trajectory, success_criteria)
            episode_results.append({"trajectory": trajectory, "reward": reward})
            
            # Update causal model from trajectory
            scm.update_from_interventions(trajectory.actions, trajectory.observations)
            
            # Update policy
            policy.update(trajectory, reward)
            
            # Check convergence
            IF is_converged(episode_results):
                BREAK
            
            # Reset environment
            env.restore_snapshot("pre_episode")
        
        # Step 5: Synthesize recipe from best trajectories
        best_trajectories = SELECT_TOP_K(episode_results, k=3, key="reward")
        recipe = synthesize_recipe(best_trajectories, dsl, scm)
        
        # Step 6: Validate on fresh Desktop 2 instances
        validation_results = validate_recipe(recipe, env, n_trials=5)
        
        IF validation_results.success_rate > 0.80:
            recipe_library.store(recipe, validation_results)
            RETURN {"status": "SUCCESS", "recipe": recipe, "validation": validation_results}
        ELSE:
            RETURN {"status": "NEEDS_MORE_TRAINING", "recipe": recipe, "validation": validation_results}
    
    FUNCTION run_episode(env, policy, subgoals, max_steps, target_app):
        
        observations = []
        actions = []
        rewards = []
        
        # Open target app on Desktop 2
        env.launch_app(target_app)
        current_state = env.capture_state()
        
        FOR step IN 1..max_steps:
            
            # Encode state
            state_vector = encode_state(current_state, subgoals)
            
            # Policy selects action (or action sequence for macro)
            action_probs = policy.predict(state_vector)
            selected_action = sample_action(action_probs)
            
            # Execute action on Desktop 2
            pre_state = current_state
            env.execute(selected_action)
            post_state = env.capture_state()
            
            # Observe outcome
            observation = {
                "pre_state": pre_state,
                "action": selected_action,
                "post_state": post_state,
                "subgoal_progress": check_subgoals(subgoals, post_state)
            }
            
            # Intermediate reward (shaping)
            step_reward = compute_shaped_reward(observation, subgoals)
            
            observations.append(observation)
            actions.append(selected_action)
            rewards.append(step_reward)
            
            current_state = post_state
            
            # Check episode termination
            IF all_subgoals_complete(subgoals, current_state):
                rewards[-1] += 10.0  # Terminal reward
                BREAK
            
            IF is_terminal_failure(current_state):
                rewards[-1] -= 5.0
                BREAK
        
        RETURN Trajectory(observations, actions, rewards)
    
    FUNCTION evaluate_trajectory(trajectory, success_criteria):
        """
        Multi-factor reward computation
        """
        
        # Factor 1: Did we achieve the goal?
        goal_reward = success_criteria.evaluate(trajectory.final_state)
        
        # Factor 2: Efficiency (fewer steps = better)
        efficiency_reward = 1.0 - (len(trajectory.actions) / MAX_STEPS)
        
        # Factor 3: Robustness (state stability)
        stability_reward = measure_state_stability(trajectory)
        
        # Factor 4: Safety (no error dialogs, crashes)
        safety_reward = 1.0 IF no_errors(trajectory) ELSE -2.0
        
        # Weighted combination
        total_reward = (
            0.5 * goal_reward +
            0.25 * efficiency_reward +
            0.15 * stability_reward +
            0.10 * safety_reward
        )
        
        RETURN total_reward
    
    FUNCTION synthesize_recipe(trajectories, dsl, scm):
        """
        Convert successful trajectories into a reusable DSL program
        """
        
        # Step 1: Find common action patterns across best trajectories
        common_sequence = longest_common_subsequence(
            [t.actions FOR t IN trajectories]
        )
        
        # Step 2: Abstract variable parts (coordinates, text inputs)
        abstracted_sequence = abstract_parameters(common_sequence, scm)
        
        # Step 3: Add conditionals from causal model
        # "IF dialog open THEN click OK ELSE click menu"
        recipe_with_conditionals = add_causal_conditionals(
            abstracted_sequence, scm
        )
        
        # Step 4: Add retry logic for uncertain actions
        recipe_with_retries = add_retry_logic(recipe_with_conditionals, scm)
        
        # Step 5: Compile to DSL
        recipe = dsl.compile(recipe_with_retries)
        
        RETURN Recipe(
            code=recipe,
            causal_graph=scm.export_subgraph(),
            description=generate_description(recipe),
            parameters=extract_parameters(recipe)
        )
```

### 1.3 Causal Model Detail

```
CLASS StructuralCausalModel:
    
    # Variables represent UI states and actions
    VARIABLES = {
        "app_state": {"type": "categorical", "values": ["closed", "open", "error"]},
        "menu_visible": {"type": "binary"},
        "dialog_open": {"type": "binary"},
        "target_element_visible": {"type": "binary"},
        "last_action": {"type": "categorical", "values": ALL_ACTIONS},
        "outcome": {"type": "categorical", "values": ["success", "fail", "noop"]}
    }
    
    FUNCTION update_from_interventions(actions, observations):
        """
        Learn causal edges from observed transitions
        """
        
        FOR t IN RANGE(len(actions)):
            action = actions[t]
            pre = observations[t].pre_state
            post = observations[t].post_state
            
            # Test each potential causal edge
            FOR var_pre IN pre.keys():
                FOR var_post IN post.keys():
                    IF var_post == var_pre:
                        CONTINUE  # No self-loops
                    
                    # Does var_pre affect var_post given action?
                    correlation = measure_association(
                        pre[var_pre], post[var_post], given=action
                    )
                    
                    IF correlation > 0.7 AND NOT has_backdoor_path(var_pre, var_post):
                        # Potential causal edge
                        add_edge(var_pre → var_post, weight=correlation, action=action)
    
    FUNCTION estimate_effect(do_action, target_variable):
        """
        Use do-calculus to estimate effect of intervention
        """
        
        # P(target | do(action)) = Σ_z P(target | action, z) P(z)
        # where z are confounders we can identify
        
        confounders = find_confounders(action, target_variable)
        
        effect_estimate = 0
        FOR z IN all_values(confounders):
            p_z = estimate_p(z)
            p_target_given_action_z = estimate_conditional(target_variable, action, z)
            effect_estimate += p_target_given_action_z * p_z
        
        RETURN effect_estimate
```

### 1.4 Convergence Criteria

```
CONVERGENCE_CHECK(episode_results):
    
    recent = LAST_N(episode_results, 5)
    
    # Criterion 1: Reward plateau
    IF STD([e.reward FOR e IN recent]) < 0.1 AND MEAN([e.reward FOR e IN recent]) > 0.8:
        RETURN "CONVERGED_HIGH_REWARD"
    
    # Criterion 2: Policy entropy collapse (policy is confident)
    recent_entropy = MEAN([policy.entropy(e.trajectory) FOR e IN recent])
    IF recent_entropy < 0.2:
        RETURN "CONVERGED_POLICY_CONFIDENT"
    
    # Criterion 3: Recipe stability (synthesized recipe unchanged)
    recent_recipes = [synthesize_recipe([e.trajectory]) FOR e IN recent]
    IF all_equal(recent_recipes):
        RETURN "CONVERGED_RECIPE_STABLE"
    
    # Criterion 4: Budget
    IF len(episode_results) >= MAX_EPISODES:
        RETURN "CONVERGED_BUDGET"
    
    # Criterion 5: Early failure (consistently failing)
    IF MEAN([e.reward FOR e IN recent]) < 0.2 AND len(recent) >= 5:
        RETURN "DIVERGING_INSPECT"
    
    RETURN "CONTINUE"
```

---

## 2. Experimentation Protocol

### 2.1 Episode Structure

| Phase | Episodes | Purpose | Exploration |
|-------|---------|---------|-------------|
| Warm-start | 1-3 | Execute from similar recipe | Low (ε=0.1) |
| Exploration | 4-10 | Discover action effects | High (ε=0.4) |
| Exploitation | 11-20 | Optimize known path | Low (ε=0.05) |
| Validation | 5 runs | Test synthesized recipe | None (deterministic) |
| **Total** | **25-28** | | |

### 2.2 Per-Episode Detail

```
EPISODE_LOOP(task_description, target_app, success_criteria):
    
    # Episode configuration
    MAX_STEPS = 50
    MAX_EPISODES = 20
    EPSILON_DECAY = 0.95  # Per episode
    
    FOR episode IN 1..MAX_EPISODES:
        
        # Configure exploration
        IF episode <= 3:
            epsilon = 0.1
            phase = "WARM_START"
        ELSE IF episode <= 10:
            epsilon = 0.4 * (EPSILON_DECAY ^ (episode - 4))
            phase = "EXPLORATION"
        ELSE:
            epsilon = max(0.05, 0.4 * (EPSILON_DECAY ^ (episode - 4)))
            phase = "EXPLOITATION"
        
        # Environment setup
        env.restore_clean_state()
        env.launch_app(target_app)
        
        # State tracking
        state = env.capture_full_state()  # Screenshot + UI tree + accessibility data
        trajectory = []
        
        FOR step IN 1..MAX_STEPS:
            
            # State encoding (128-dim vector)
            state_vector = [
                # App state features (32-dim)
                encode_window_position(state),
                encode_menu_state(state),
                encode_dialog_state(state),
                
                # Task progress features (32-dim)
                encode_subgoal_progress(subgoals, state),
                encode_target_proximity(state),
                
                # History features (32-dim)
                encode_last_actions(trajectory, window=5),
                encode_action_frequencies(trajectory),
                
                # Context features (32-dim)
                encode_time_of_day(),
                encode_desktop2_load(),
                encode_recent_errors(trajectory)
            ]
            
            # Action selection
            IF random() < epsilon:
                # Random exploration: sample from safe actions only
                action = sample_safe_random_action(state, macro_actions)
            ELSE:
                # Policy exploitation
                action_probs = policy.predict(state_vector)
                action = argmax(action_probs)
            
            # Execute action
            pre_screenshot = env.screenshot()
            env.execute(action)
            post_screenshot = env.screenshot()
            
            # Observe outcome
            observation = {
                "step": step,
                "pre_state": pre_screenshot,
                "action": action,
                "post_state": post_screenshot,
                "ui_changes": diff_ui_trees(pre_screenshot, post_screenshot),
                "error_detected": env.has_error_dialog(),
                "app_crashed": env.is_app_running(target_app)
            }
            
            # Compute reward
            reward = compute_reward(observation, subgoals, step)
            
            trajectory.append({"state": state_vector, "action": action, "reward": reward})
            
            # Update state
            state = env.capture_full_state()
            
            # Check termination
            IF success_criteria.evaluate(state):
                trajectory[-1]["reward"] += 10.0
                BREAK
            
            IF env.has_error_dialog() OR NOT env.is_app_running(target_app):
                trajectory[-1]["reward"] -= 5.0
                BREAK
        
        # Post-episode
        episode_reward = SUM([t["reward"] FOR t IN trajectory])
        
        # Update policy (PPO)
        advantages = compute_gae_advantages(trajectory, gamma=0.99, lambda=0.95)
        policy.update(trajectory, advantages)
        
        # Update causal model
        scm.update_from_interventions(
            [t["action"] FOR t IN trajectory],
            [t["state"] FOR t IN trajectory]
        )
        
        # Check convergence
        IF CONVERGENCE_CHECK(all_episodes) != "CONTINUE":
            BREAK
    
    # Synthesize recipe from top 3 episodes
    top_episodes = SELECT_TOP_K(all_episodes, 3, key="reward")
    recipe = synthesize_recipe(top_episodes, dsl, scm)
    
    RETURN recipe
```

### 2.3 Example: "Learn Photoshop dark photo editing"

```
TASK: "Learn how to edit dark photos intelligently in Photoshop"

subgoals = [
    "Open Photoshop",
    "Open dark photo file",
    "Access adjustment layers",
    "Apply brightness/contrast correction",
    "Apply shadow/highlight recovery",
    "Fine-tune with curves",
    "Export edited image"
]

success_criteria = {
    "before_after_similarity": "< 0.3",  # Image should change significantly
    "no_crash": True,
    "export_exists": True,
    "edit_steps_count": ">= 3"
}

macro_actions_available = [
    "click(x, y)",
    "double_click(x, y)",
    "right_click(x, y)",
    "type(text)",
    "hotkey(keys)",
    "drag(start, end)",
    "scroll(amount)",
    "wait(seconds)",
    "menu_select(menu_path)",
    "dialog_click(button)",
    "slider_set(name, value)",
    "layer_select(name)",
    "adjustment_apply(type, params)"
]

# Learned recipe (synthesized DSL):
RECIPE "Photoshop Dark Photo Enhancement":
    REQUIRE app: "Adobe Photoshop"
    
    STEP 1: open_file("{input_image_path}")
    
    STEP 2: IF NOT layer_exists("Brightness/Contrast"):
        menu_select(["Layer", "New Adjustment Layer", "Brightness/Contrast"])
    
    STEP 3: adjustment_set("Brightness/Contrast", brightness=+30, contrast=+15)
    
    STEP 4: menu_select(["Image", "Adjustments", "Shadow/Highlight"])
    
    STEP 5: dialog_set("Shadows", amount=+50)
    STEP 6: dialog_set("Highlights", amount=-20)
    STEP 7: dialog_click("OK")
    
    STEP 8: IF image_histogram.peak < 0.3:  # Very dark
        menu_select(["Layer", "New Adjustment Layer", "Curves"])
        curves_lift_midtones(amount=+20)
    
    STEP 9: export_as("{output_image_path}", quality=95)
    
    PARAMETERS:
        input_image_path: "Path to dark photo"
        output_image_path: "Path for edited output"
        brightness_adjust: "+30 (default, learned)"
```

### 2.4 Credit Consumption Model

| Component | Per Episode | Credits | Notes |
|-----------|------------|---------|-------|
| Desktop 2 VM time (5 min) | 1 | ~8 | Minimal compute |
| Screenshot capture + diff | 50 | ~2 | Local processing |
| UI tree analysis | 50 | ~3 | Accessibility API |
| State encoding (LLM assist) | 50 | ~10 | Claude Haiku for state summary |
| Policy update | 1 | ~5 | Local compute |
| Recipe synthesis | 1 | ~25 | Claude Sonnet for DSL generation |
| Validation (5 runs) | 5 | ~40 | Full recipe execution test |
| **Per learning session** | **20-25 episodes** | **~600-750** | |

**Optimized target**: $0.25 = ~250 credits
- Reuse similar recipes → reduce episodes to 10-12
- Use local VLM for screenshot understanding → save ~200 credits
- Batch validation runs → save ~20 credits
- **Optimized total: ~250-350 credits**

---

## 3. Data Collection & Feature Engineering

### 3.1 Raw Data Collected

```json
{
  "session_id": "agent_2024_0515_001",
  "task": "Photoshop dark photo editing",
  "timestamp_start": "2024-05-15T09:00:00Z",
  "timestamp_end": "2024-05-15T09:25:00Z",
  
  "environment": {
    "desktop2_os": "Windows 11",
    "target_app": "Adobe Photoshop 2024",
    "app_version": "25.4.0",
    "screen_resolution": "1920x1080",
    "ui_scale": "100%"
  },
  
  "episodes": [
    {
      "episode_id": 1,
      "phase": "warm_start",
      "epsilon": 0.1,
      "steps": [
        {
          "step": 1,
          "state_hash": "sha256_abc",
          "state_description": "Photoshop splash screen visible",
          "action": {"type": "wait", "params": {"seconds": 3}},
          "reward": 0.1,
          "pre_ui_tree": {...},
          "post_ui_tree": {...},
          "screenshot_pre": "ep1_s1_pre.png",
          "screenshot_post": "ep1_s1_post.png"
        },
        {
          "step": 2,
          "action": {"type": "menu_select", "params": {"path": ["File", "Open"]}},
          "reward": 0.2,
          "outcome": "Dialog opened successfully"
        }
        // ... more steps
      ],
      "terminal_reward": 7.5,
      "success": true,
      "steps_to_success": 12,
      "errors": [],
      "recipe_fragment": "open_file -> menu_select(File, Open) -> ..."
    }
  ],
  
  "causal_model": {
    "edges_learned": [
      {"from": "menu_select(File,Open)", "to": "dialog_open", "strength": 0.95},
      {"from": "click(Open button)", "to": "file_loaded", "strength": 0.88},
      {"from": "adjustment_set(Brightness)", "to": "image_histogram", "strength": 0.92}
    ],
    "interventions_tested": 15,
    "confounders_identified": ["app_load_state", "dialog_focus"]
  },
  
  "final_recipe": {
    "dsl_code": "RECIPE 'Photoshop Dark Photo Enhancement' ...",
    "validation_success_rate": 0.88,
    "avg_execution_time_sec": 45,
    "parameters": ["input_image_path", "output_image_path"]
  }
}
```

### 3.2 Feature Engineering Pipeline

```
ENCODE_STATE(full_state, subgoals):
    
    # 1. Visual features (from screenshot)
    screenshot = full_state.screenshot
    visual_features = []
    
    # Resize to 224x224, extract with lightweight CNN
    resized = resize(screenshot, (224, 224))
    visual_embedding = mobilenet_v2.encode(resized)  # 1280-dim → PCA to 64-dim
    
    # Detect specific UI elements via template matching
    menu_bar_visible = detect_template(screenshot, "menu_bar_template")
    dialog_visible = detect_template(screenshot, "dialog_template")
    toolbar_visible = detect_template(screenshot, "toolbar_template")
    
    visual_features = [visual_embedding, menu_bar_visible, dialog_visible, toolbar_visible]
    
    # 2. UI tree features (from accessibility tree)
    ui_tree = full_state.accessibility_tree
    
    tree_features = {
        "element_count": count_elements(ui_tree),
        "max_depth": tree_depth(ui_tree),
        "focused_element_type": get_focused_element(ui_tree).type,
        "menu_items_count": count_by_role(ui_tree, "menuitem"),
        "button_count": count_by_role(ui_tree, "button"),
        "dialog_count": count_by_role(ui_tree, "dialog"),
        "editable_count": count_by_role(ui_tree, "textbox")
    }
    
    # 3. Task progress features
    progress_features = []
    FOR subgoal IN subgoals:
        progress = estimate_subgoal_progress(subgoal, ui_tree, screenshot)
        progress_features.append(progress)
    
    overall_progress = MEAN(progress_features)
    nearest_subgoal_index = argmax(progress_features)
    
    # 4. Historical features
    history_features = {
        "steps_taken": len(trajectory),
        "unique_actions_used": len(set(t.action FOR t IN trajectory)),
        "repeated_actions": count_repeated_patterns(trajectory),
        "error_count": count_errors(trajectory),
        "time_since_start": elapsed_time()
    }
    
    # Concatenate and normalize
    RETURN normalize(concat(visual_features, tree_features, progress_features, history_features))
```

### 3.3 Domain/Task Classification

```
FUNCTION classify_agent_task(task_description):
    
    # Keywords map to app categories
    app_keyword_map = {
        "photoshop": "Adobe Photoshop",
        "edit photo": "Adobe Photoshop",
        "spreadsheet": "Microsoft Excel",
        "excel": "Microsoft Excel",
        "browser": "Google Chrome",
        "web": "Google Chrome",
        "terminal": "Windows Terminal",
        "command": "Windows Terminal",
        "code": "Visual Studio Code",
        "programming": "Visual Studio Code",
        "document": "Microsoft Word",
        "write": "Microsoft Word",
        "presentation": "Microsoft PowerPoint",
        "slide": "Microsoft PowerPoint"
    }
    
    task_lower = task_description.lower()
    
    # Detect target app
    detected_apps = []
    FOR keyword, app IN app_keyword_map:
        IF keyword IN task_lower:
            detected_apps.append(app)
    
    target_app = detected_apps[0] IF detected_apps ELSE "unknown"
    
    # Extract subgoals using LLM decomposition
    subgoals = llm_decompose_task(task_description, target_app)
    
    # Generate success criteria
    success_criteria = generate_success_criteria(task_description, subgoals)
    
    RETURN {
        "target_app": target_app,
        "subgoals": subgoals,
        "success_criteria": success_criteria,
        "estimated_difficulty": estimate_difficulty(subgoals)
    }
```

---

## 4. Model Storage & Retrieval

### 4.1 Learned Model Schema

```json
{
  "model_version": "agent_v1.0",
  "created_at": "2024-05-15T09:25:00Z",
  
  "recipe": {
    "recipe_id": "photoshop_dark_photo_edit_v1",
    "recipe_name": "Photoshop Dark Photo Enhancement",
    "description": "Intelligently brighten and recover shadow detail in underexposed photos using adjustment layers",
    
    "dsl_code": "RECIPE 'Photoshop Dark Photo Enhancement' { ... }",
    
    "target_app": {
      "name": "Adobe Photoshop",
      "version_constraint": ">= 2023",
      "os": ["Windows", "macOS"]
    },
    
    "parameters": [
      {
        "name": "input_image_path",
        "type": "file_path",
        "required": true,
        "description": "Path to the dark photo to edit"
      },
      {
        "name": "output_image_path",
        "type": "file_path",
        "required": true,
        "description": "Where to save the enhanced image"
      },
      {
        "name": "brightness_adjust",
        "type": "integer",
        "default": 30,
        "range": [0, 100],
        "description": "Brightness increase amount"
      }
    ],
    
    "causal_graph": {
      "nodes": [
        "open_file", "menu_select", "adjustment_layer_created",
        "brightness_set", "shadow_highlight_open", "export_complete"
      ],
      "edges": [
        {"from": "open_file", "to": "adjustment_layer_created", "weight": 0.95},
        {"from": "brightness_set", "to": "export_complete", "weight": 0.88}
      ],
      "conditional_branches": [
        {
          "condition": "histogram_peak < 0.3",
          "if_true": ["curves_adjustment"],
          "if_false": []
        }
      ]
    },
    
    "validation_results": {
      "success_rate": 0.88,
      "trials_count": 5,
      "avg_execution_time_sec": 45,
      "failure_modes": [
        {"mode": "dialog_not_responding", "count": 1, "recovery": "wait_then_retry"}
      ]
    },
    
    "execution_history": [
      {"timestamp": "2024-05-15T10:00:00Z", "user": "user_42", "success": true, "duration_sec": 42}
    ]
  },
  
  "policy_checkpoint": {
    "network_weights": "base64_encoded...",
    "optimizer_state": "base64_encoded...",
    "episode_count": 18,
    "final_reward": 8.2
  },
  
  "meta": {
    "learning_duration_min": 25,
    "episodes_run": 18,
    "credit_consumed": 320,
    "desktop2_snapshots_created": 18,
    "causal_edges_discovered": 12
  }
}
```

### 4.2 Retrieval & Matching

```
FUNCTION match_recipe_to_request(user_task_description):
    
    task_emb = embed(user_task_description)
    
    # Step 1: Exact app match + task similarity
    candidates = []
    FOR recipe IN recipe_library:
        app_match = recipe.target_app IN extract_apps(user_task_description)
        task_similarity = cosine_similarity(task_emb, embed(recipe.description))
        
        IF app_match AND task_similarity > 0.8:
            candidates.append((recipe, task_similarity, "exact_match"))
    
    # Step 2: Fuzzy task match across apps
    IF NOT candidates:
        FOR recipe IN recipe_library:
            task_similarity = cosine_similarity(task_emb, embed(recipe.description))
            IF task_similarity > 0.85:
                candidates.append((recipe, task_similarity, "fuzzy_task"))
    
    # Step 3: Subgoal overlap
    IF NOT candidates:
        user_subgoals = llm_decompose_task(user_task_description)
        FOR recipe IN recipe_library:
            overlap = jaccard_similarity(
                set(user_subgoals),
                set(recipe.extracted_subgoals)
            )
            IF overlap > 0.6:
                candidates.append((recipe, overlap, "subgoal_overlap"))
    
    # Step 4: No match → trigger learning
    IF NOT candidates:
        RETURN {
            "action": "TRIGGER_LEARNING",
            "message": "No recipe found for this task. I can learn it on Desktop 2 (takes ~20 min, ~$0.25).",
            "estimated_cost": "$0.25",
            "estimated_time": "20 minutes"
        }
    
    # Select best candidate
    candidates.sort(key=lambda x: x[1], reverse=True)
    best = candidates[0]
    
    RETURN {
        "action": "EXECUTE_RECIPE",
        "recipe": best[0],
        "match_type": best[2],
        "confidence": best[1],
        "missing_parameters": identify_missing_params(best[0], user_task_description)
    }
```

### 4.3 Confidence Thresholds

| Recipe Match Confidence | Action | User Interaction |
|--------------------------|--------|------------------|
| ≥ 0.90 + validation > 0.85 | Auto-execute with parameters filled | "Executing recipe for [task]..." toast |
| 0.75 - 0.89 | Execute with confirmation | "I found a recipe for [task]. Run it?" dialog |
| 0.60 - 0.74 | Show recipe, let user modify | Recipe preview with editable parameters |
| 0.40 - 0.60 | Suggest learning new recipe | "Similar recipes exist. Learn a new one?" |
| < 0.40 | Trigger learning | "I can learn this task on Desktop 2" |

### 4.4 Fallback Behavior

```
FUNCTION fallback_agent(task_description):
    
    # No recipe, user declines learning
    IF user_declines_learning:
        RETURN {
            "action": "PROVIDE_GUIDANCE",
            "response": generate_text_guidance(task_description),
            "message": "I can provide step-by-step instructions instead."
        }
    
    # Learning failed on Desktop 2
    IF learning_failed:
        RETURN {
            "action": "ESCALATE",
            "message": "This task is too complex to learn automatically. Please provide a more specific description.",
            "suggestions": suggest_simpler_decompositions(task_description)
        }
    
    # Recipe execution failed on Desktop 1
    IF recipe_execution_failed:
        # Try recovery from causal model
        recovery = causal_recovery(recipe, failure_point)
        IF recovery:
            RETURN {"action": "RECOVER", "recovery_steps": recovery}
        ELSE:
            RETURN {
                "action": "MANUAL_INTERVENTION",
                "message": "Recipe failed at step [N]. Please take over.",
                "current_state": capture_current_state()
            }
```

---

## 5. Integration Points

### 5.1 TuneHub Base Class Interface

```python
class AgentTuner(TuneHubBase):
    """
    Recipe-learning tuner for app automation.
    """
    
    def __init__(self, hub_config):
        super().__init__(hub_config)
        self.recipe_library = RecipeLibrary()
        self.policy = PPO_Policy()
        self.scm = StructuralCausalModel()
        self.dsl = AgentRecipeDSL()
        self.env = None  # Desktop 2 connection established on demand
        
    def register_with_hub(self, hub):
        hub.register_tuner(
            name="agent",
            trigger_events=["AUTOMATION_REQUEST", "RECIPE_VALIDATION", "RECIPE_EXECUTION"],
            output_format="recipe_or_execution",
            priority=3  # Lower: only triggers on explicit requests
        )
    
    def on_event(self, event_type, payload):
        
        IF event_type == "AUTOMATION_REQUEST":
            # User asked to automate a task
            match = self.match_recipe_to_request(payload.task_description)
            
            IF match.action == "EXECUTE_RECIPE":
                # Execute existing recipe
                RETURN self.execute_recipe(match.recipe, payload.parameters)
            
            IF match.action == "TRIGGER_LEARNING":
                # Start learning session on Desktop 2
                RETURN self.start_learning_session(
                    task=payload.task_description,
                    target_app=payload.target_app,
                    success_criteria=payload.success_criteria
                )
        
        IF event_type == "RECIPE_VALIDATION":
            # Periodic validation check
            result = self.validate_on_desktop2(payload.recipe)
            IF result.status == "DEGRADED":
                # App version changed, re-learn
                RETURN self.trigger_relearning(payload.recipe)
        
        IF event_type == "RECIPE_EXECUTION":
            # Execute recipe on Desktop 1
            execution_result = self.execute_recipe(
                recipe=payload.recipe,
                parameters=payload.parameters,
                target="desktop1"
            )
            
            IF NOT execution_result.success:
                # Try causal recovery
                recovery = self.causal_recovery(payload.recipe, execution_result.failure_point)
                RETURN recovery IF recovery ELSE {"action": "MANUAL_INTERVENTION"}
    
    def start_learning_session(self, task, target_app, success_criteria):
        # Establish Desktop 2 connection
        self.env = Desktop2Environment.connect()
        
        # Run learning loop
        recipe = self.learn_recipe(task, target_app, success_criteria)
        
        # Store if successful
        IF recipe.validation.success_rate > 0.80:
            self.recipe_library.store(recipe)
            RETURN {"status": "SUCCESS", "recipe_id": recipe.recipe_id}
        ELSE:
            RETURN {"status": "FAILED", "reason": "insufficient_validation"}
```

### 5.2 Desktop 1 vs Desktop 2 Responsibilities

| Responsibility | Desktop 1 (Main) | Desktop 2 (Isolated) |
|---------------|------------------|---------------------|
| Recipe execution (user tasks) | Primary | N/A |
| Recipe learning (exploration) | Orchestration only | Full execution |
| App state capture | N/A | Screenshot + UI tree + a11y |
| Policy training | Lightweight updates | Full PPO batch updates |
| Causal model updates | Merge results | Discover edges |
| Recipe validation | Trigger + review | Execute 5 trials |
| Snapshot management | Catalog | Create/restore |
| Safety containment | N/A | Full isolation |
| Credit billing | Track | Execute APIs |

```
# Desktop 2 isolation architecture
Desktop2Environment:
    - Isolated VM/container
    - No network access to Desktop 1
    - Pre-installed app suite (Photoshop, Office, Chrome, VS Code)
    - Snapshot capability: save/restore full system state
    - Headless operation: VNC for debugging only
    - API: execute_action(action) → observation
    - API: capture_state() → {screenshot, ui_tree, accessibility}
    - API: save_snapshot(name) / restore_snapshot(name)
    - API: launch_app(app_name)
    - API: reset_to_clean()
```

### 5.3 APIs Needed

| Feature | API | Purpose |
|---------|-----|---------|
| Desktop 2 | `connect()` | Establish secure channel |
| Desktop 2 | `execute_action(action)` | Run macro on isolated env |
| Desktop 2 | `capture_state()` | Get screenshot + UI tree |
| Desktop 2 | `save/restore_snapshot()` | Episode reset |
| Core LLM | `generate(prompt)` | Task decomposition |
| Core LLM | `generate(dsl_code)` | Recipe synthesis |
| Core VLM | `analyze_screenshot(img)` | Visual state understanding |
| Credit Manager | `charge(credits, "agent_learning")` | Per-session billing |
| User Profile | `get_installed_apps()` | Available apps for learning |
| Settings | `register_settings_panel()` | Recipe management UI |
| UI Framework | `show_progress_bar()` | Learning progress |
| UI Framework | `show_recipe_preview()` | Recipe preview before run |

---

## 6. Implementation Phases

### Phase 1: MVP (Weeks 1-4)
**Goal**: Basic macro recording + playback, single app

```
- [ ] Desktop 2 environment setup (VM with target apps)
- [ ] Macro action library: click, type, hotkey, menu_select, wait
- [ ] Simple recorder: record user actions on Desktop 2
- [ ] Simple player: replay recorded actions
- [ ] Recipe storage: JSON with action sequence
- [ ] Task matching: keyword-based recipe lookup
- [ ] Single app support: Photoshop or Chrome
- [ ] Validation: manual check (user confirms success)
```

**Success criteria:**
- Can record and replay a 5-step action sequence
- Replay success rate ≥ 70% on identical initial state
- User can save/load named recipes

**Credit target:** ≤ 500 (manual recording, minimal learning)

---

### Phase 2: Enhanced (Weeks 5-8)
**Goal**: Reinforcement learning, causal model, DSL synthesis

```
- [ ] PPO policy implementation (state → action)
- [ ] State encoder: screenshot + UI tree → feature vector
- [ ] Reward shaping: subgoal progress + efficiency + safety
- [ ] Causal model: learn action → outcome edges
- [ ] Recipe DSL: compile successful trajectories to reusable code
- [ ] Parameter abstraction: detect variable parts (file paths, values)
- [ ] Multi-app support: 5+ target applications
- [ ] Automatic validation: 5-run success rate test
- [ ] Recipe library: similarity search, version management
```

**Success criteria:**
- Learned recipe success rate ≥ 80% on validation
- Recipe execution time ≤ 2x human speed
- Can handle conditional branches (IF dialog open THEN...)

**Credit target:** ≤ 350 per recipe (optimized learning)

---

### Phase 3: Polish (Weeks 9-10)
**Goal**: Robustness, recovery, generalization

```
- [ ] Causal recovery: use SCM to recover from failures
- [ ] App version adaptation: detect UI changes, adjust recipe
- [ ] Parameter inference: auto-fill parameters from user context
- [ ] Recipe chaining: combine recipes for complex workflows
- [ ] Safety constraints: hardcoded forbidden actions (delete system files)
- [ ] Learning from failure: negative examples improve policy
- [ ] Recipe marketplace: share recipes across users (anonymized)
- [ ] Performance: recipe execution < 50% overhead vs manual
```

**Success criteria:**
- Recipe recovery rate ≥ 60% (self-healing from common failures)
- App version change detection accuracy ≥ 90%
- Zero safety incidents (no harmful actions)

**Credit target:** ≤ 250 per recipe (transfer learning from recipe library)

---

## 7. Validation Strategy

### 7.1 A/B Testing

```
FUNCTION ab_test_recipe(recipe, control="manual_execution"):
    
    # Compare recipe execution vs manual task completion
    
    control_group = {
        "method": "manual",
        "task": recipe.description,
        "completion_time": measure_manual_time(),
        "success_rate": 1.0,  # User always succeeds eventually
        "user_satisfaction": survey_manual_users()
    }
    
    treatment_group = {
        "method": "recipe",
        "task": recipe.description,
        "completion_time": measure_recipe_time(),
        "success_rate": recipe.validation.success_rate,
        "user_satisfaction": survey_recipe_users()
    }
    
    # Metrics
    time_savings = (control.completion_time - treatment.completion_time) / control.completion_time
    
    # Primary: time savings without significant success rate drop
    IF time_savings > 0.30 AND treatment.success_rate > 0.75:
        RETURN "SIGNIFICANT_IMPROVEMENT"
    
    IF treatment.success_rate < 0.60:
        RETURN "RELIABILITY_REGRESSION"
    
    IF time_savings < 0.10:
        RETURN "INSUFFICIENT_VALUE"
    
    RETURN "ACCEPTABLE"
```

### 7.2 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Recipe success rate | ≥ 80% | Successful executions / Total executions |
| Time savings vs manual | ≥ 30% | (manual_time - recipe_time) / manual_time |
| Learning cost | ≤ $0.25 | Credits consumed / Recipe learned |
| Validation pass rate | ≥ 80% | 5-run validation success rate |
| Recovery rate | ≥ 60% | Self-recovered failures / Total failures |
| Recipe generalization | ≥ 70% | Success on varied inputs / Success on training input |
| User satisfaction | ≥ 4.0 / 5 | Post-execution rating |
| Safety incidents | 0 | Count of harmful/disruptive actions |

### 7.3 Tune Rejection Criteria

```
FUNCTION validate_agent_tune(recipe):
    
    rejections = []
    
    # Criterion 1: Validation failure
    IF recipe.validation.success_rate < 0.60:
        rejections.append("LOW_VALIDATION_SUCCESS")
    
    # Criterion 2: Unreliable causal model
    IF recipe.causal_graph.edge_count < 3:
        rejections.append("INSUFFICIENT_CAUSAL_MODEL")
    
    # Criterion 3: Safety concerns
    IF contains_risky_actions(recipe.dsl_code):
        rejections.append("SAFETY_CONCERN")
    
    # Criterion 4: Too many steps (inefficient)
    IF recipe.estimated_steps > 50:
        rejections.append("INEFFICIENT")
    
    # Criterion 5: A/B test failure
    ab_result = ab_test_recipe(recipe)
    IF ab_result == "RELIABILITY_REGRESSION":
        rejections.append("AB_TEST_FAILURE")
    
    # Criterion 6: User override frequency
    IF get_user_override_rate(recipe.recipe_id) > 0.30:
        rejections.append("HIGH_USER_OVERRIDE")
    
    IF rejections:
        RETURN {"status": "REJECTED", "reasons": rejections}
    ELSE:
        RETURN {"status": "APPROVED", "confidence": recipe.validation.success_rate}
```

### 7.4 Retry Strategy

```
FUNCTION handle_rejected_agent(recipe, reasons):
    
    FOR reason IN reasons:
        
        IF reason == "LOW_VALIDATION_SUCCESS":
            # Need more exploration episodes
            additional_episodes = 5
            # Increase exploration in problematic states
            policy.epsilon_boost = 0.3
        
        IF reason == "INSUFFICIENT_CAUSAL_MODEL":
            # Force more diverse interventions
            exploration_strategy = "causal_intervention_focused"
            # Target states where causal edges are missing
        
        IF reason == "SAFETY_CONCERN":
            # Add safety constraints to action filter
            action_filter.add_constraint("no_file_deletion")
            action_filter.add_constraint("no_network_requests")
            # Re-synthesize recipe with safe action subset
            RETURN resynthesize_with_safety_constraints(recipe)
        
        IF reason == "INEFFICIENT":
            # Add efficiency bonus to reward function
            reward_function.efficiency_weight *= 1.5
            additional_episodes = 3
        
        IF reason == "AB_TEST_FAILURE":
            # Inspect failure modes
            failure_analysis = analyze_failure_patterns(recipe)
            IF failure_analysis.app_version_mismatch:
                RETURN {"action": "FLAG_APP_CHANGED", "needs_relearning": True}
        
        IF reason == "HIGH_USER_OVERRIDE":
            # Switch to more conservative execution
            recipe.auto_execute = False
            recipe.require_confirmation = True
            # Learn from overrides as negative examples
            incorporate_negative_examples(recipe)
    
    # Run additional learning if needed
    IF additional_episodes:
        FOR i IN RANGE(additional_episodes):
            learn_recipe(recipe.task_description, recipe.target_app, recipe.success_criteria)
    
    RETURN re_validate(recipe)
```

---

# APPENDIX: CROSS-CUTTING CONCERNS

## A. TuneHub Base Class Specification

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class TuneEvent:
    event_type: str
    payload: Dict[str, Any]
    timestamp: float
    session_id: str

@dataclass
class TuneResult:
    action: str  # "APPLY", "SUGGEST", "LEARN", "PASS"
    data: Dict[str, Any]
    confidence: float
    source: str  # "learned", "heuristic", "default"

class TuneHubBase(ABC):
    """
    Abstract base class for all tuners in TuneHub.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.observations = []
        self.learned_model = None
        self.is_converged = False
    
    @abstractmethod
    def register_with_hub(self, hub: 'TuneHub') -> None:
        """Register this tuner with the central TuneHub."""
        pass
    
    @abstractmethod
    def on_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[TuneResult]:
        """Handle events from the TuneHub event bus."""
        pass
    
    @abstractmethod
    def get_learned_model(self) -> Dict[str, Any]:
        """Serialize learned state for persistence."""
        pass
    
    @abstractmethod
    def load_learned_model(self, model_data: Dict[str, Any]) -> None:
        """Hydrate from stored model."""
        pass
    
    @abstractmethod
    def check_convergence(self) -> str:
        """Return convergence status."""
        pass
    
    def record_observation(self, observation: Dict[str, Any]) -> None:
        """Default observation recording."""
        self.observations.append({
            **observation,
            "recorded_at": time.time()
        })
    
    def get_observation_count(self) -> int:
        return len(self.observations)
```

## B. Credit Budget Summary

| Tuner | Phase 1 Credits | Phase 2 Credits | Phase 3 Credits | Production Target |
|-------|----------------|-----------------|-----------------|-------------------|
| RePrompt | 2,000 | 1,500 | 1,200 | 1,200/task |
| Dictation | 300 | 1,200 | 800 | 800/domain |
| Agent | 500 | 350/recipe | 250/recipe | 250/recipe |

## C. Convergence Status Definitions

| Status | Meaning | Action |
|--------|---------|--------|
| `CONVERGED_HIGH_QUALITY` | Blend/recipe achieves > 85% quality | Deploy to production |
| `CONVERGED_EXPLORATION_DONE` | Acquisition function flat, no more to learn | Deploy if quality acceptable |
| `CONVERGED_STABLE` | Variation below threshold | Deploy |
| `CONVERGED_AUTO_APPLY` | Auto-apply rate acceptable | Deploy |
| `CONVERGED_BUDGET` | Budget exhausted | Deploy best-so-far or retry |
| `DIVERGING_REVIEW_NEEDED` | Performance degrading or unstable | Investigate and retry |
| `INSUFFICIENT_DATA` | Not enough observations | Continue learning |
| `LEARNING` | Active learning in progress | Continue |

## D. Shared Utilities

```python
# utils/feature_extraction.py
# utils/convergence.py
# utils/ab_testing.py
# utils/credit_tracker.py
# utils/model_persistence.py

# All tuners share:
# - Embedding model (SentenceTransformer)
# - Credit tracking interface
# - A/B testing framework
# - Model serialization format (JSON + optional binary weights)
# - Convergence checking utilities
# - Event bus communication protocol
```

---

*Document generated for wiztant Engineering Team*
*Tune Hub — Universal Meta-Learning System*
