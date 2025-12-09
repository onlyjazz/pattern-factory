Perfect — here is a **complete storyboard-style test protocol** showing:

1. **Initial CONTENT extraction output (with realistic mistakes)**
2. **Failure at `model.verifyUpsert`**
3. **Routing through Capo → No.sendMessageToChat**
4. **Human correction**
5. **Return to Capo and successful retry**

This is a fully coherent end-to-end test you can use to validate your **entire put-and-take architecture**.

---

# 🧪 **TEST PROTOCOL STORYBOARD — CONTENT Flow With HITL Error Recovery**

---

# **STEP 1 — Capo receives a CONTENT request**

This could originate from user input, ingestion, or frontend call.

```json
{
  "verb": "CONTENT",
  "nextAgent": "model.Capo",
  "returnCode": "OK",
  "messageBody": {
    "url": "https://example.com/post123",
    "markup": "<html>...</html>",
    "content_source": "substack"
  }
}
```

---

# **STEP 2 — Capo routes to model.requestToExtractEntities**

```json
{
  "verb": "CONTENT",
  "nextAgent": "model.requestToExtractEntities",
  "returnCode": "OK",
  "messageBody": {
    "url": "https://example.com/post123",
    "markup": "<html>...</html>",
    "content_source": "substack"
  }
}
```

---

# **STEP 3 — model.requestToExtractEntities returns an *invalid* payload**

Two realistic extraction errors appear here:

* `org.name` is missing
* a pattern-to-post link references a post name that does not exist

```json
{
  "verb": "CONTENT",
  "nextAgent": "model.verifyUpsert",
  "returnCode": "OK",
  "messageBody": {
    "orgs": [
      {
        "description": "an AI-first biotech CRO",
        "tech_keywords": ["ai", "biotech"],
        "content_url": "https://example.com/post123",
        "content_source": "substack"
      }
    ],
    "guests": [],
    "posts": [
      {
        "name": "Inside the Future of Biotech Automation",
        "description": "A deep dive into automation trends",
        "keywords": ["automation", "labs", "ai"],
        "content_url": "https://example.com/post123",
        "content_source": "substack",
        "published_at": null
      }
    ],
    "patterns": [
      {
        "pattern_code": "PROCESS_POWER",
        "name": "Process Power",
        "description": "Improving efficiency through structured workflows",
        "kind": "pattern",
        "content_url": "https://example.com/post123",
        "content_source": "substack"
      }
    ],
    "pattern_post_link": [
      { "pattern_code": "PROCESS_POWER", "post_name": "NON_EXISTENT_POST" }
    ],
    "pattern_org_link": [],
    "pattern_guest_link": []
  }
}
```

---

# **STEP 4 — model.verifyUpsert detects errors**

* Missing `org.name`
* Link to missing post

It emits an ERROR:

```json
{
  "verb": "CONTENT",
  "nextAgent": "No.sendMessageToChat",
  "returnCode": "ERROR",
  "messageBody": {
    "error": "Validation failed",
    "reason": "org.name is missing; pattern_post_link references unknown post 'NON_EXISTENT_POST'.",
    "example_fix": "Add org.name and update post_name to an existing post."
  }
}
```

---

# **STEP 5 — Capo routes this to No.sendMessageToChat**

```json
{
  "verb": "ERROR",
  "nextAgent": "No.sendMessageToChat",
  "returnCode": "ERROR",
  "messageBody": {
    "error": "Validation failed",
    "reason": "org.name is missing; pattern_post_link references unknown post.",
    "example_fix": "Add org.name and fix post_name."
  }
}
```

---

# **STEP 6 — No.sendMessageToChat explains the issue to the human**

### UI-facing message (paraphrased):

> The upsert cannot continue.
>
> * The organization is missing a required field: name.
> * The pattern_post_link references a non-existent post: “NON_EXISTENT_POST”.
>
> Please provide:
>
> * The correct org.name
> * A corrected post_name (must match an existing post)

**Human inputs correction:**

```json
{
  "orgs": [
    { "name": "HelixBio", "description": "an AI-first biotech CRO" }
  ],
  "pattern_post_link": [
    { "pattern_code": "PROCESS_POWER", "post_name": "Inside the Future of Biotech Automation" }
  ]
}
```

---

# **STEP 7 — No.sendMessageToChat wraps the correction and returns control to Capo**

```json
{
  "verb": "CONTENT",
  "nextAgent": "model.Capo",
  "returnCode": "OK",
  "messageBody": {
    "orgs": [
      { "name": "HelixBio", "description": "an AI-first biotech CRO" }
    ],
    "pattern_post_link": [
      { "pattern_code": "PROCESS_POWER", "post_name": "Inside the Future of Biotech Automation" }
    ]
  }
}
```

---

# **STEP 8 — Capo reroutes the corrected payload back to model.verifyUpsert**

```json
{
  "verb": "CONTENT",
  "nextAgent": "model.verifyUpsert",
  "returnCode": "OK",
  "messageBody": {
    "orgs": [
      { "name": "HelixBio", "description": "an AI-first biotech CRO" }
    ],
    "pattern_post_link": [
      { "pattern_code": "PROCESS_POWER", "post_name": "Inside the Future of Biotech Automation" }
    ]
  }
}
```

---

# **STEP 9 — model.verifyUpsert validates successfully**

```json
{
  "verb": "CONTENT",
  "nextAgent": "tool.executeSQL",
  "returnCode": "OK",
  "messageBody": {
    "jsonb_payload": {
      "orgs": [...],
      "guests": [...],
      "posts": [...],
      "patterns": [...],
      "pattern_post_link": [...],
      "pattern_org_link": [...],
      "pattern_guest_link": [...]
    }
  }
}
```

---

# **STEP 10 — tool.executeSQL performs the upsert and returns success**

```json
{
  "verb": "CONTENT",
  "nextAgent": "model.Capo",
  "returnCode": "OK",
  "messageBody": {
    "status": "success",
    "rows_affected": 4
  }
}
```

---

# 🎉 **This fully validates your Markov-chain architecture**

You can use this storyboard as:

* a **manual QA flow**
* a **test fixture** for your frontend + Pitboss
* a **debugging reference** for agent chain failures
* a **unit test** for each agent’s behavior

---

If you want, I can also generate:

### ✓ A *successful* test storyboard (no errors, clean flow)

### ✓ A *malformed JSON* error test

### ✓ A *pattern inconsistency* test suite

### ✓ A *load test* with multiple posts and patterns

### ✓ A mocked SQL execution walkthrough for `tool.executeSQL`

Which one would you like next?
