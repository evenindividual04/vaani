# AI & Prompting Strategy

The intelligence of the Vaani agent is heavily structured. We do not rely on a single, massive prompt telling the LLM to "act like an insurance agent." Instead, we use state-based constrained prompting to ensure compliance and deterministic outcomes.

## 🧠 Finite State Machine (FSM) Prompting

The FSM controls the *context* given to the LLM at any given time.

### How it works:
1. **System Base Prompt**: A minimal set of universal rules (e.g., "You are Vaani, an AI assistant for insurance claims. Be polite, concise, and do not hallucinate policy details.").
2. **State Injection**: Depending on the FSM's current state, specific instructions are appended to the system prompt.
   - *If state = `POLICY_VERIFY`*: "Your current objective is strictly to ask for and verify the user's 6-digit policy number. Do not ask about the incident until you have the policy number."
   - *If state = `INCIDENT_CAPTURE`*: "Your objective is to determine if this is an auto, home, or medical claim. Ask clarifying questions if necessary."
3. **Data Extraction Schema**: Along with generating a conversational response, the LLM is instructed (often via OpenAI function calling/structured outputs) to output a JSON object representing the fields it has successfully extracted from the transcript so far.

## 📊 FNOL Data Schema

The ultimate goal of the AI is to populate the First Notice of Loss (FNOL) JSON object. 

```json
{
  "policy_number": "string | null",
  "incident_type": "enum(auto, home, medical, other) | null",
  "incident_date": "ISO8601 | null",
  "incident_location": "string | null",
  "injuries_reported": "boolean | null",
  "vehicle_damage": "string | null",
  "third_party_involved": "boolean | null",
  "callback_number": "string | null"
}
```

The system calculates a `completeness_score` based on how many required fields in this schema are non-null. The FSM only advances to the `SUMMARY` state once the score reaches an acceptable threshold.

## 🧪 Evaluation Suite (`/eval`)

Because tweaking prompts can lead to regressions, Vaani includes an evaluation suite. 

### Simulated Transcripts
We maintain a library of mock user transcripts (e.g., "Angry customer who won't give their policy number", "Rambling caller who gives details out of order"). 

### The CI/CD Pipeline
When a prompt is updated, the `/eval/run` endpoint feeds these simulated transcripts into the LLM. 
The system asserts:
1. Did the LLM extract the correct `policy_number`?
2. Did the LLM stay within the bounds of the FSM state?
3. Did the LLM output JSON strictly matching the schema?

The Next.js frontend visualizes these results on the `/eval` page, preventing bad prompts from reaching production.
