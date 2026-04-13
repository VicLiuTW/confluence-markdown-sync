## 文件版本

| 版本 | 撰寫人 | 更新日期 | 說明 |
|------|--------|----------|------|
| v1.0 | author | 2024-01-15 | Initial version |

---

## 1. Document Positioning

| Item | Description |
|------|-------------|
| Scope | (What this spec covers) |
| Target Audience | (Who should read this) |
| Prerequisites | (Related specs or background knowledge) |
| Out of Scope | (What this spec does NOT cover) |

---

## 2. Overview

(Brief description of the feature/module — what it does, why it exists, key constraints.)

---

## 3. Functional Requirements

### 3.1 (Requirement Group A)

| # | Requirement | Priority | Notes |
|---|-------------|----------|-------|
| 1 | (Describe requirement) | Must | |
| 2 | (Describe requirement) | Should | |

### 3.2 (Requirement Group B)

(Continue with more requirement groups as needed.)

---

## 4. Data Model

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string | Yes | Unique identifier |
| name | string | Yes | Display name |
| status | enum | Yes | ACTIVE, INACTIVE, PENDING |
| created_at | datetime | Yes | Creation timestamp |

---

## 5. API / Interface

```
POST /api/v1/resource
```

Request:

```json
{
  "name": "example",
  "status": "ACTIVE"
}
```

Response:

```json
{
  "id": "res-001",
  "name": "example",
  "status": "ACTIVE",
  "created_at": "2024-01-15T10:00:00Z"
}
```

| Status | Code | Description |
|--------|------|-------------|
| 200 | OK | Success |
| 400 | BAD_REQUEST | Validation error |
| 404 | NOT_FOUND | Resource not found |

---

## 6. Business Rules

1. (Rule description — when X happens, the system should Y)
2. (Rule description)
3. (Rule description)

---

## 7. UI / Interaction (if applicable)

(Describe screen layout, user flow, or reference wireframes.)

![wireframe](../images/wireframe-example.png)

---

## 8. Open Questions

| # | Question | Status | Resolution |
|---|----------|--------|------------|
| 1 | (Unresolved question) | Open | |
| 2 | (Resolved question) | Closed | (Decision made) |
