# BENCHMARK TASK SUITE FOR AGENT TESTING
# (stateful reasoning in stateless environment)

## DESIGN RATIONALE

### Task Requirements Analysis
- **Objective:** Test visual recognition, target tracking, and state change detection
- **Challenge:** Agent must distinguish between "unmarked red circle" and "marked/partially covered circle"
- **Avoid:** Duplicate clicks on already-marked targets
- **Key Skill:** Update internal target count as circles are eliminated

### Linguistic Strategy for 2B Model
1. **Explicit state definition:** Define what constitutes a "remaining target"
2. **Negative examples:** State what NOT to click (already marked circles)
3. **Verification instruction:** Check screenshot after each click to confirm change
4. **Count enforcement:** Explicitly state "5 targets total, stop when all 5 are marked"

---

## BENCHMARK TASK 1: EXPLICIT TARGET ELIMINATION

```
I have Microsoft Paint open with 5 large red circles visible on a white canvas. Your job is to click on each red circle exactly once to mark it with black paint.

CURRENT TOOL STATE: The brush tool is active with a large circular black brush. When you click anywhere, a black circle will appear at that location.

TARGET DEFINITION: A red circle is a valid target ONLY if it is still predominantly red. Once you click on a red circle, it becomes partially or fully covered with black paint and is NO LONGER a valid target.

TASK RULES:
1. There are exactly 5 red circles total
2. Click on each red circle once
3. After clicking a circle, it will have black paint on it
4. Do NOT click circles that already have black paint on them (they are no longer targets)
5. After each click, verify the result in the screenshot before deciding next action
6. Stop when all 5 circles have black marks on them

COMPLETION CRITERIA: When you see 5 circles with black paint on them (no pure red circles remaining), the task is complete.

Start by observing the screen to locate all 5 red circles, then click them one by one.
```

**Why This Works:**
- States total count explicitly (5 circles)
- Defines target state change: "predominantly red" → "has black paint"
- Negative instruction: "Do NOT click circles that already have black paint"
- Forces verification: "After each click, verify the result"
- Clear completion signal: "no pure red circles remaining"

---

## BENCHMARK TASK 2: STATE-BASED TARGET TRACKING

```
Open Microsoft Paint window is visible on screen. Inside the canvas, there are 5 large red circular shapes. You have a black circular brush tool already selected and active.

YOUR MISSION: Mark all 5 red circles by clicking on them with the black brush. Each click will place a black circle at the click location.

IMPORTANT DISTINCTIONS:
- VALID TARGET: A red circle that is completely red (no black paint on it yet)
- INVALID TARGET: A red circle that has been clicked and now has black paint covering part of it
- You must distinguish between "pristine red circle" (click it) and "red circle with black mark" (already processed, skip it)

OPERATIONAL PROCEDURE:
1. Take a screenshot and count how many pristine red circles you see
2. Click on ONE pristine red circle
3. Take a screenshot to verify the circle now has a black mark
4. Update your count: subtract 1 from remaining targets
5. Repeat steps 1-4 until no pristine red circles remain

COMPLETION: When your screenshot shows 5 circles that all have black marks on them, declare mission accomplished.

Do NOT click the same circle twice. If a circle has any black paint on it from a previous click, it is no longer a target.
```

**Why This Works:**
- Introduces "pristine" vs "marked" terminology (concrete distinction)
- Numbered procedure (easier for 2B model to follow)
- Explicit count update instruction (maintain target inventory)
- Emphasizes verification between actions
- Redundant "do NOT click same circle twice" (critical for success)

---

## BENCHMARK TASK 3: VISUAL DIFFERENTIAL TARGET DEFINITION

```
Microsoft Paint is open showing a white canvas with 5 large red circles drawn on it. The black circular brush tool is currently active and selected. When you click anywhere on the canvas, a black circle will be painted at that position.

GOAL: Apply black paint to all 5 red circles by clicking on each one exactly once.

TARGET IDENTIFICATION RULES:
- CLICK THIS: Red circle with no black paint → this is an active target
- DO NOT CLICK THIS: Red circle with black paint partially covering it → this target is already complete
- DO NOT CLICK THIS: Red circle that is mostly black → this target is already complete

The key test: After you click a red circle, that specific circle changes appearance (black paint covers part of it). When choosing your next target, you must identify which circles still look completely red versus which circles have changed due to your previous clicks.

EXECUTION STEPS:
1. Observe screen: identify all circles that are purely red (no black marks)
2. Count how many pure red circles remain
3. Click on one pure red circle
4. Observe screen again: verify that circle now has black paint on it
5. Recognize that circle is no longer a valid target
6. Repeat steps 1-5 until all 5 circles have black marks

STOP CONDITION: When your screenshot analysis shows zero circles that are purely red (all 5 have black marks), the task is complete.

Each click changes one circle's state from "target" to "completed". Track this change visually.
```

**Why This Works:**
- Three-part negative definition (shows what NOT to click with variations)
- Emphasizes visual change detection: "that specific circle changes appearance"
- Introduces "state change tracking" concept explicitly
- Stop condition uses "zero circles that are purely red" (forces counting remaining targets, not completed targets)
- Final sentence summarizes core concept: "track state change visually"

---

## TESTING PROTOCOL

### Evaluation Criteria

| Metric | Success Threshold | Measurement Method |
|--------|------------------|-------------------|
| **Duplicate Clicks** | 0 | Count clicks on already-marked circles |
| **Target Identification** | 100% | Agent must locate all 5 circles in first observation |
| **State Change Recognition** | ≥4/5 | Agent must acknowledge circle is marked after clicking it |
| **Completion Accuracy** | Exactly 5 clicks | Total click_element calls targeting circles |
| **Verification Cycles** | ≥5 | observe_screen calls after each click |
| **False Completion** | 0 | Agent must not declare completion with unmarked circles remaining |

### Expected Failure Modes (2B Model)

1. **Count Drift:** Agent loses track of how many circles remain
   - Detection: Plan states "3 circles remaining" when screenshot shows 4
   - Mitigation: Explicit counting instruction in each plan

2. **Visual Similarity Confusion:** Clicks same circle twice because black mark is small
   - Detection: Two consecutive clicks with overlapping coordinates
   - Mitigation: "predominantly red" vs "has any black" distinction

3. **Premature Completion:** Declares success after 4/5 circles
   - Detection: "GOAL ACHIEVED" in plan when screenshot shows 1 red circle
   - Mitigation: Explicit "5 total" count in multiple places

4. **No State Tracking:** Doesn't update target list after each click
   - Detection: Plan says "5 circles visible" on turn 3 (after 2 clicks)
   - Mitigation: "subtract 1 from remaining" instruction

### Comparison Baseline (8B Model Expected Performance)

- **Turns to completion:** 11-13 (5 clicks + 6-8 observations)
- **Duplicate clicks:** 0
- **Self-corrections:** 0-1 (may re-verify uncertain circle)
- **Plan quality:** Will explicitly track "Remaining: 4/5", "Remaining: 3/5", etc.

### 2B Model Success Criteria

- **Acceptable turn count:** ≤20 turns
- **Acceptable duplicate clicks:** ≤1 (allows one mistake with self-correction)
- **Required self-correction:** If duplicate click occurs, next plan must state "Previously clicked circle X, will not click again"
- **Plan tracking:** Must mention remaining target count in at least 3/5 action plans

---

## RECOMMENDED TESTING SEQUENCE

1. **Run Task 2 first** (most structured, numbered procedure)
2. **If Task 2 succeeds, run Task 3** (tests visual differential ability)
3. **If Task 2 fails, run Task 1** (simpler language, more explicit)

**Rationale:** Task 2 provides most scaffolding (numbered steps), Task 3 has most sophisticated target definition, Task 1 is clearest baseline.

### Setup Instructions

1. Open Microsoft Paint
2. Select red color, brush tool
3. Draw 5 large circles (approximately 100-150px diameter) spaced across canvas
4. Select black color, ensure brush tool active
5. Verify brush is large (should be visible as circular cursor)
6. Move cursor away from circles (to avoid confusion)
7. Take manual screenshot to confirm setup
8. Paste task text into agent input

### Log Analysis Checklist

After each benchmark run, verify in logs:
- [ ] Agent identifies all 5 circles in first observation
- [ ] Agent uses observe_screen after each click
- [ ] Plan messages track remaining target count
- [ ] No clicks occur on coordinates matching previously-clicked circles (±50px tolerance)
- [ ] Completion declared only when plan states "0 red circles remaining" or equivalent

This benchmark suite tests the critical "stateful reasoning in stateless environment" challenge - the agent must maintain an evolving target list using only visual feedback and plan transmission.
