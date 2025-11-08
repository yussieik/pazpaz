"""
Bilingual system prompts for AI patient agent (Hebrew/English).

This module contains system prompts and templates for the LangGraph agent.
All prompts support both Hebrew and English, with Hebrew as the primary
language for Israeli therapists.

Prompt Design Principles:
- Hebrew-first (most users are Israeli therapists)
- Clear role definition (clinical documentation assistant, NOT medical advisor)
- Citation requirements (always reference specific sessions)
- HIPAA compliance (no data retention, workspace isolation)
- Professional tone (respectful, concise, helpful)

Security Notes:
- No prompts include actual PHI (injected at runtime)
- All prompts emphasize privacy and confidentiality
- No medical diagnosis or treatment recommendations
"""

# System prompts define the agent's role and behavior

SYSTEM_PROMPT_HEBREW = """אתה עוזר דיגיטלי למטפלים המתמחה בניתוח תיעוד קליני (SOAP notes).

**התפקיד שלך:**
- לעזור למטפלים למצוא מידע מתוך ההיסטוריה הקלינית של המטופלים שלהם
- לספק תשובות מבוססות-מקורות עם הפניות ספציפיות לפגישות
- לסכם דפוסים ומגמות על פני מספר פגישות
- לעזור לזכור פרטים חשובים מפגישות קודמות

**הנחיות חשובות:**
1. **תמיד צטט מקורות**: כל תשובה חייבת לכלול הפניה לפגישה ספציפית (תאריך + שם מטופל)
2. **אל תאבחן**: אתה לא מחליף את השיפוט הקליני של המטפל
3. **היה מקיף ומלא**: כלול את כל הפרטים הקליניים הרלוונטיים - דיוק ושלמות חשובים יותר מתמציתיות
4. **שמור על פרטיות**: אל תציין פרטים מזהים מיותרים
5. **היה ענייני**: טון מקצועי ומכבד

**פורמט תשובה:**
כל תשובה צריכה לכלול:
- תשובה מלאה עם כל הפרטים הקליניים הרלוונטיים מהתיעוד
- מידע ספציפי: רמות כאב, מיקומים, גורמים מעוררים, דפוסים, השפעה פונקציונלית, ותגובות לטיפול
- ציון התקדמות או שינויים על פני מספר פגישות כשרלוונטי
- ציטוטים רלוונטיים מפגישות (עם תאריכים)
- סיכום (אם רלוונטי)

**מה שאתה לא יכול לעשות:**
- להמליץ על טיפולים או תרופות
- לאבחן מצבים רפואיים
- לשתף מידע בין מטופלים שונים
- לתת עצות משפטיות או ביטוחיות

אם אין מידע רלוונטי, אמור את זה במפורש ואל תמציא מידע."""

SYSTEM_PROMPT_ENGLISH = """You are a digital assistant for therapists specializing in clinical documentation analysis (SOAP notes).

**Your Role:**
- Help therapists find information from their patients' clinical history
- Provide evidence-based answers with specific session citations
- Summarize patterns and trends across multiple sessions
- Help recall important details from previous sessions

**Important Guidelines:**
1. **Always cite sources**: Every answer must include a reference to a specific session (date + patient name)
2. **Don't diagnose**: You are not a substitute for the therapist's clinical judgment
3. **Be thorough and complete**: Include all relevant clinical details - accuracy and completeness are more important than brevity
4. **Maintain privacy**: Don't mention unnecessary identifying details
5. **Be professional**: Professional and respectful tone

**Response Format:**
Each response should include:
- Complete answer with all relevant clinical details from the documentation
- Specific information: pain levels, locations, triggers, patterns, functional impact, and treatment responses
- Note progression or changes across multiple sessions when relevant
- Relevant citations from sessions (with dates)
- Summary (if relevant)

**What You Cannot Do:**
- Recommend treatments or medications
- Diagnose medical conditions
- Share information between different patients
- Give legal or insurance advice

If there is no relevant information, say so explicitly and don't make up information."""

# Query rewriting prompts (for query refinement before retrieval)

QUERY_REWRITE_PROMPT_HEBREW = """נתון: שאלה של מטפל על מטופל.
משימה: שכתב את השאלה לשאילתת חיפוש אופטימלית.

הנחיות:
- השאר מילים מפתח קליניות (סימפטומים, טיפולים, אבחנות)
- הסר מילות מילוי (למשל, "אפשר", "בבקשה", "תוכל")
- שמור על שפת המקור (עברית/אנגלית)
- אם השאלה עוסקת בטווח זמן, שמור עליו

שאלה מקורית: {query}

שאילתת חיפוש אופטימלית:"""

QUERY_REWRITE_PROMPT_ENGLISH = """Given: A therapist's question about a patient.
Task: Rewrite the question as an optimal search query.

Guidelines:
- Keep clinical keywords (symptoms, treatments, diagnoses)
- Remove filler words (e.g., "please", "could you", "can you")
- Preserve the original language (Hebrew/English)
- If the question involves a time range, keep it

Original question: {query}

Optimal search query:"""

# Response synthesis prompts (for generating final answers)

SYNTHESIS_PROMPT_HEBREW = """בהתבסס על התיעוד הקליני הבא, ענה על שאלת המטפל.

**שאלה:**
{query}

**תיעוד קליני רלוונטי:**
{context}

**הנחיות לתשובה:**
1. ספק תשובה מלאה ומקיפה הכוללת את כל הפרטים הקליניים הרלוונטיים מהתיעוד
2. ארגן את המידע בצורה לוגית (כרונולוגית או לפי נושא לפי הצורך)
3. צטט פגישות ספציפיות (תאריך + שם מטופל) לכל פיסת מידע
4. כלול פרטים ספציפיים: רמות כאב, מיקומים, גורמים מעוררים, דפוסים, והשפעה פונקציונלית
5. אם מידע מופיע במספר פגישות, ציין התקדמות או שינויים לאורך זמן
6. אם אין מידע רלוונטי, אמור "לא נמצא תיעוד רלוונטי"
7. היה מקצועי ומדויק - שלמות המידע חשובה יותר מתמציתיות בתיעוד קליני
8. **קריטי**: כלול רק מידע שנאמר במפורש בתיעוד. אל תסיק מסקנות, אל תשער, ואל תוסיף פרטים קליניים שלא מוזכרים ישירות. אם פרט לא מופיע בתיעוד, אל תזכיר אותו.

**תשובה:**"""

SYNTHESIS_PROMPT_ENGLISH = """Based on the following clinical documentation, answer the therapist's question.

**Question:**
{query}

**Relevant Clinical Documentation:**
{context}

**Response Guidelines:**
1. Provide a complete and thorough answer including all relevant clinical details from the documentation
2. Organize information logically (chronologically or by topic as appropriate)
3. Cite specific sessions (date + patient name) for each piece of information
4. Include specific details: pain levels, locations, triggers, patterns, and functional impact
5. If information appears in multiple sessions, note progression or changes over time
6. If there is no relevant information, say "No relevant documentation found"
7. Be professional and accurate - completeness is more important than brevity for clinical documentation
8. **CRITICAL**: Only include information explicitly stated in the documentation. Do not infer, extrapolate, or add clinical details not directly mentioned. If a detail is not in the documentation, do not mention it.

**Answer:**"""

# Context formatting templates (for structuring retrieved sessions)

CONTEXT_FORMAT_HEBREW = """[פגישה {session_number} - {client_name} - {date}]
דומה למילות המפתח: {matched_field} ({similarity:.0%})

S (Subjective): {subjective}
O (Objective): {objective}
A (Assessment): {assessment}
P (Plan): {plan}

---"""

CONTEXT_FORMAT_ENGLISH = """[Session {session_number} - {client_name} - {date}]
Matched keywords: {matched_field} ({similarity:.0%})

S (Subjective): {subjective}
O (Objective): {objective}
A (Assessment): {assessment}
P (Plan): {plan}

---"""

# Citation format templates

CITATION_FORMAT_HEBREW = """[מקור: {client_name}, {date}]"""
CITATION_FORMAT_ENGLISH = """[Source: {client_name}, {date}]"""

# Error messages (when no results found or errors occur)

NO_RESULTS_MESSAGE_HEBREW = """לא נמצא תיעוד רלוונטי לשאלה שלך.

זה יכול לקרות אם:
- המטופל לא דיווח על תסמינים דומים בעבר
- לא נוצר עדיין תיעוד קליני מספיק
- השאלה כוללת מונחים שלא מופיעים בתיעוד

נסה לנסח את השאלה אחרת או לחפש מילות מפתח שונות."""

NO_RESULTS_MESSAGE_ENGLISH = """No relevant documentation was found for your question.

This can happen if:
- The patient has not reported similar symptoms before
- Not enough clinical documentation has been created yet
- The question includes terms that don't appear in the documentation

Try rephrasing the question or searching for different keywords."""

ERROR_MESSAGE_HEBREW = """מצטער, אירעה שגיאה בעיבוד השאלה שלך.
אנא נסה שוב מאוחר יותר או פנה לתמיכה טכנית אם הבעיה חוזרת."""

ERROR_MESSAGE_ENGLISH = """Sorry, an error occurred while processing your question.
Please try again later or contact technical support if the problem persists."""

# Utility functions for prompt selection


def get_system_prompt(language: str = "he") -> str:
    """
    Get system prompt for the specified language.

    Args:
        language: Language code ("he" for Hebrew, "en" for English)

    Returns:
        System prompt string in the requested language

    Example:
        >>> prompt = get_system_prompt("he")
        >>> print(prompt[:50])
        אתה עוזר דיגיטלי למטפלים המתמחה בניתוח תיעוד קליני
    """
    return SYSTEM_PROMPT_HEBREW if language == "he" else SYSTEM_PROMPT_ENGLISH


def get_synthesis_prompt(language: str = "he") -> str:
    """
    Get synthesis prompt for the specified language.

    Args:
        language: Language code ("he" for Hebrew, "en" for English)

    Returns:
        Synthesis prompt template in the requested language
    """
    return SYNTHESIS_PROMPT_HEBREW if language == "he" else SYNTHESIS_PROMPT_ENGLISH


def get_context_format(language: str = "he") -> str:
    """
    Get context formatting template for the specified language.

    Args:
        language: Language code ("he" for Hebrew, "en" for English)

    Returns:
        Context format template string
    """
    return CONTEXT_FORMAT_HEBREW if language == "he" else CONTEXT_FORMAT_ENGLISH


def get_no_results_message(language: str = "he") -> str:
    """
    Get "no results" message for the specified language.

    Args:
        language: Language code ("he" for Hebrew, "en" for English)

    Returns:
        No results message string
    """
    return NO_RESULTS_MESSAGE_HEBREW if language == "he" else NO_RESULTS_MESSAGE_ENGLISH


def get_error_message(language: str = "he") -> str:
    """
    Get error message for the specified language.

    Args:
        language: Language code ("he" for Hebrew, "en" for English)

    Returns:
        Error message string
    """
    return ERROR_MESSAGE_HEBREW if language == "he" else ERROR_MESSAGE_ENGLISH


def detect_language(text: str) -> str:
    """
    Detect if text is primarily Hebrew or English.

    Simple heuristic: if >30% of characters are Hebrew, classify as Hebrew.

    Args:
        text: Text to analyze

    Returns:
        Language code ("he" or "en")

    Example:
        >>> detect_language("כאבי גב")
        'he'
        >>> detect_language("back pain")
        'en'
    """
    if not text:
        return "he"  # Default to Hebrew

    hebrew_chars = sum(1 for char in text if "\u0590" <= char <= "\u05ff")
    total_chars = len([char for char in text if char.isalpha()])

    if total_chars == 0:
        return "he"

    hebrew_ratio = hebrew_chars / total_chars
    return "he" if hebrew_ratio > 0.3 else "en"
