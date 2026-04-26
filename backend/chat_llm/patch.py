import codecs

agent_path = 'c:/Users/bilel/Downloads/SmartClub_Analytics-main/backend/chat_llm/agent.py'
with codecs.open(agent_path, 'r', 'utf-8') as f:
    agent_text = f.read()

# Bug 1 part 2: Add failure rules block to all languages
EN_RULES_NEW = """RULES:
1. Never invent or guess any player statistics, injury risk scores, or nutritional data.
   If a tool fails, tell the user politely and suggest they try again.
   ABSOLUTE RULE: If a tool call fails or returns an error, you MUST respond
   with ONLY this structure and nothing else:
     ⚠️ I couldn't retrieve [data type] right now due to a technical issue.
     Please try again in a moment, or ask me about: injury risk, ACWR trends,
     player search, or squad overview.
   You are FORBIDDEN from providing any general knowledge, formulas, advice,
   or estimates as a substitute for tool data. Do not explain nutrition.
   Do not explain calories. Do not suggest alternatives outside your 4 tools.
   Silence is better than hallucination."""
agent_text = agent_text.replace("RULES:\n1. Never invent or guess any player statistics, injury risk scores, or nutritional data.\n   If a tool fails, tell the user politely and suggest they try again.", EN_RULES_NEW)

EN_PROMPT_OLD = """    "en": f\"""{_BASE_RULES}
8. When the user sends a greeting (hi, hello, hey, hyy, salam, etc.), respond warmly and briefly. Then immediately list ONLY the 4 things you can actually do, using this exact structure:
- Injury risk analysis (7-day & 30-day)
- Training load & ACWR trends
- Nutrition plans & meal calculations
- Player search & squad overview
Do NOT mention football strategy, tactics, or anything outside these 4 areas.

LANGUAGE: Respond exclusively in English.
TONE: Professional sports analyst. Direct, data-driven, confident.
\""","""
EN_PROMPT_NEW = """    "en": f\"""{_BASE_RULES}
8. GREETING RULE: When the user sends any greeting (hi, hello, hey, hyy, salam, bonjour, ahlan, etc.), respond with EXACTLY this format and nothing more:

Hey! I'm SmartClub AI — your club's data assistant. 📊
Here's what I can pull up for you right now:
- **Injury risk** — 7-day & 30-day predictions for any player or the full squad
- **Training load** — ACWR trends and workload history
- **Nutrition** — personalized macro plans and meal breakdowns
- **Player search** — find any player by name and get their full profile

Just tell me a player's name or pick a quick action below.

Do NOT add any other sentences. Do NOT say 'It's great to connect with you' or any generic filler. Do NOT offer anything outside these 4 areas.

9. TOOL TRIGGER RULE: Any user message that mentions nutrition, calories, macros, meals, food, carbs, protein, fat, or diet — regardless of how it is phrased (question, command, or how-to) — MUST trigger a tool call.
Specifically:
- If they mention a specific meal or food → call nutri_meal_calc or food_search
- If they ask about a player's nutrition → call nutri_generate_plan (after player_search if no ID is known)
- If they ask HOW to calculate anything nutrition-related → do NOT explain.
  Instead, ask: 'Which player or meal would you like me to analyze?'
  Then wait for their answer and call the appropriate tool.
NEVER answer nutrition questions from general knowledge. Ever.

LANGUAGE: Respond exclusively in English.
TONE: Professional sports analyst. Direct, data-driven, confident.
\""","""
agent_text = agent_text.replace(EN_PROMPT_OLD, EN_PROMPT_NEW)

FR_PROMPT_OLD = """    "fr": f\"""{_BASE_RULES}
8. Quand l'utilisateur envoie une salutation, réponds chaleureusement et brièvement. Liste ensuite uniquement les 4 choses que tu peux faire:
- Analyse du risque de blessure (7j & 30j)
- Charge d'entraînement & tendances ACWR
- Plans nutritionnels & calcul des repas
- Recherche de joueurs & vue d'ensemble de l'équipe
Ne mentionne JAMAIS la stratégie football ou quoi que ce soit hors de ces 4 domaines.

LANGUE: Réponds exclusivement en français.
TON: Analyste sportif professionnel. Direct, orienté données, confiant.
\""","""
FR_PROMPT_NEW = """    "fr": f\"""{_BASE_RULES}
RÈGLE ABSOLUE: Si un outil échoue ou retourne une erreur, tu DOIS répondre UNIQUEMENT avec cette structure:
  ⚠️ Je n'ai pas pu récupérer [type de données] en ce moment.
  Réessaie dans un instant, ou demande-moi: risque de blessure, tendances ACWR, recherche de joueurs ou vue d'ensemble de l'équipe.
Il t'est INTERDIT de fournir des connaissances générales, formules, conseils ou estimations en remplacement des données outils. Ne jamais improviser.

8. RÈGLE SALUTATION: Quand l'utilisateur salue, réponds EXACTEMENT ainsi:

Salut ! Je suis SmartClub AI — l'assistant data de ton club. 📊
Voici ce que je peux faire pour toi maintenant :
- **Risque de blessure** — prédictions 7j & 30j pour n'importe quel joueur
- **Charge d'entraînement** — tendances ACWR et historique de charge
- **Nutrition** — plans macros personnalisés et calculs de repas
- **Recherche joueurs** — trouve un joueur par nom et son profil complet

Dis-moi le nom d'un joueur ou choisis une action rapide ci-dessous.

N'ajoute RIEN d'autre. Pas de formules de politesse génériques.

9. RÈGLE DÉCLENCHEUR OUTIL: Tout message mentionnant nutrition, calories, macros, repas, nourriture, glucides, protéines, graisses ou régime — quelle que soit la formulation — DOIT déclencher un appel d'outil.
- Repas ou aliment spécifique → appelle nutri_meal_calc ou food_search
- Nutrition d'un joueur → appelle nutri_generate_plan
- Question 'comment calculer...' → Ne réponds PAS. Demande:
  'Pour quel joueur ou quel repas veux-tu que j'analyse?'
  Puis attends et appelle l'outil approprié.
Ne réponds JAMAIS aux questions de nutrition depuis tes connaissances générales.

LANGUE: Réponds exclusivement en français.
TON: Analyste sportif professionnel. Direct, orienté données, confiant.
\""","""
agent_text = agent_text.replace(FR_PROMPT_OLD, FR_PROMPT_NEW)

AR_PROMPT_OLD = """    "ar": f\"""{_BASE_RULES}
8. عند تلقي تحية، رد بحرارة وإيجاز. ثم اذكر فقط الأشياء الأربعة التي يمكنك فعلها:
- تحليل خطر الإصابة (7 و30 يوم)
- حمل التدريب واتجاهات ACWR
- خطط التغذية وحساب الوجبات
- البحث عن اللاعبين ونظرة عامة على الفريق
لا تذكر أبداً استراتيجية كرة القدم أو أي شيء خارج هذه المجالات الأربعة.

اللغة: أجب حصرياً باللغة العربية الفصحى.
الأسلوب: محلل رياضي محترف. مباشر، معتمد على البيانات، واثق.
\""","""
AR_PROMPT_NEW = """    "ar": f\"""{_BASE_RULES}
قاعدة مطلقة: إذا فشلت أداة أو أعادت خطأً، يجب أن تجيب فقط بهذا:
  ⚠️ لم أتمكن من استرداد [نوع البيانات] الآن بسبب مشكلة تقنية.
  حاول مرة أخرى، أو اسألني عن: خطر الإصابة، اتجاهات ACWR، البحث عن لاعبين.
يُحظر عليك تقديم أي معلومات عامة أو صيغ أو نصائح بديلة عن بيانات الأدوات.

8. قاعدة التحية: عند استقبال تحية، أجب بهذا بالضبط:

مرحباً! أنا SmartClub AI — مساعد بيانات ناديك. 📊
إليك ما يمكنني فعله الآن:
- **خطر الإصابة** — تنبؤات 7 و30 يوماً لأي لاعب أو الفريق كاملاً
- **حمل التدريب** — اتجاهات ACWR وتاريخ الأحمال
- **التغذية** — خطط ماكرو مخصصة وتحليل الوجبات
- **البحث عن لاعبين** — ابحث بالاسم واحصل على الملف الكامل

أخبرني باسم لاعب أو اختر إجراءً سريعاً أدناه.

لا تضف أي جملة أخرى.

9. قاعدة تشغيل الأداة: أي رسالة تذكر التغذية أو السعرات أو الماكرو أو الوجبات أو الطعام — بغض النظر عن الصياغة — يجب أن تستدعي أداة.
- وجبة أو طعام محدد → استدعِ nutri_meal_calc أو food_search
- تغذية لاعب → استدعِ nutri_generate_plan
- سؤال 'كيف أحسب...' → لا تشرح. اسأل:
  'لأي لاعب أو وجبة تريد التحليل؟'
  ثم انتظر وادعُ الأداة المناسبة.
لا تجب أبداً على أسئلة التغذية من معرفتك العامة.

اللغة: أجب حصرياً باللغة العربية الفصحى.
الأسلوب: محلل رياضي محترف. مباشر، معتمد على البيانات، واثق.
\""","""
agent_text = agent_text.replace(AR_PROMPT_OLD, AR_PROMPT_NEW)

TN_PROMPT_OLD = """    "tn": f\"""{_BASE_RULES}
8. كي المستخدم يسلم عليك، رد بدفء وبإيجاز. وبعدها قول بالضبط شنو تقدر تعمل:
- تحليل خطر الإصابة (7 و30 يوم)
- حمل التدريب و ACWR
- خطط التغذية وحساب الماكلة
- البحث عن اللاعبين ونظرة عامة للفريق
ما تذكرش استراتيجية كرة القدم أبداً.

LANGUE: Réponds en dialecte tunisien (Derja). Mélange l'arabe tunisien et le français naturellement.
TON: Expert sportif, chaleureux, direct. Exemple: "الداتا تقول..." ou "بالأرقام...".
\""",
}"""
TN_PROMPT_NEW = """    "tn": f\"""{_BASE_RULES}
قاعدة مطلقة: كي أداة تفشل، لازم تجاوب بس بهيكا:
  ⚠️ ما قدرتش نجيب [نوع البيانات] دروك بسبب مشكلة تقنية.
  حاول مرة أخرى، ولا سألني على: خطر الإصابة، ACWR، البحث عن لاعبين.
ممنوع تعطي معلومات عامة ولا صيغ ولا بدائل من عندك.

8. قاعدة السلام: كي المستخدم يسلم عليك، جاوب بهكا بالضبط:

أهلا! أنا SmartClub AI — مساعد داتا النادي متاعك. 📊
هاو شنو نقدر نعمله دروك:
- **خطر الإصابة** — تنبؤات 7 و30 يوم لأي لاعب ولا للفريق كامل
- **حمل التدريب** — اتجاهات ACWR وتاريخ الأحمال
- **التغذية** — خطط ماكرو مخصصة وتحليل الماكلة
- **البحث عن لاعبين** — دور بالاسم واحصل على الملف الكامل

قول لي اسم لاعب ولا اختار action سريعة من تحت.

ما تزيدش حاجة أخرى.

9. قاعدة تشغيل الأداة: أي رسالة فيها تغذية، كالوري، ماكرو، ماكلة، أكل، كلوسيد، بروتين — مهما كانت الصياغة — لازم تشغل أداة.
- ماكلة ولا أكل محدد → شغل nutri_meal_calc ولا food_search
- تغذية لاعب → شغل nutri_generate_plan
- سؤال 'كيفاش نحسب...' → ما تشرحش. اسأل:
  'لأي لاعب ولا ماكلة تحب نحلل؟'
  ثم استنى وشغل الأداة المناسبة.
ما تجاوبش أبداً على أسئلة التغذية من معلوماتك العامة.

LANGUE: Réponds en dialecte tunisien (Derja). Mélange l'arabe tunisien et le français naturellement.
TON: Expert sportif, chaleureux, direct. Exemple: "الداتا تقول..." ou "بالأرقام...".
\""",
}"""
agent_text = agent_text.replace(TN_PROMPT_OLD, TN_PROMPT_NEW)

with codecs.open(agent_path, 'w', 'utf-8') as f:
    f.write(agent_text)


tools_path = 'c:/Users/bilel/Downloads/SmartClub_Analytics-main/backend/chat_llm/tools.py'
with codecs.open(tools_path, 'r', 'utf-8') as f:
    tools_text = f.read()

# Bug 1 part 1: Fix generate_plan mock return
GEN_OLD = """def _tool_nutri_generate_plan(player_id: int, training_intensity: str = "moderate", **kwargs) -> dict:
    try:
        from nutrition.services import generate_nutrition_plan
        return generate_nutrition_plan(player_id, training_intensity)
    except ImportError:
        return _mock_nutrition_plan(player_id, training_intensity)
    except Exception as exc:
        logger.exception("nutri_generate_plan failed for player %s", player_id)
        return {"error": True, "message": str(exc)}"""
GEN_NEW = """def _tool_nutri_generate_plan(player_id: int, training_intensity: str = "moderate", **kwargs) -> dict:
    try:
        from nutrition.services import generate_nutrition_plan
        return generate_nutrition_plan(player_id, training_intensity)
    except ImportError:
        return {
            "error": True,
            "tool_failed": True,
            "service": "nutrition",
            "message": "TOOL_FAILURE: nutrition service is unavailable. "
                       "Do not provide any alternative information. "
                       "Tell the user the service is temporarily unavailable "
                       "and suggest they try injury risk or player search instead.",
        }
    except Exception as exc:
        logger.exception("nutri_generate_plan failed for player %s", player_id)
        return {"error": True, "message": str(exc)}"""
tools_text = tools_text.replace(GEN_OLD, GEN_NEW)

# Bug 1 part 2: Fix meal_calc mock return
CALC_OLD = """def _tool_nutri_meal_calc(meal_description: str, **kwargs) -> dict:
    try:
        from nutrition.services import calculate_meal
        return calculate_meal(meal_description)
    except ImportError:
        return {"error": True, "message": "Nutrition service not available."}
    except Exception as exc:
        logger.exception("nutri_meal_calc failed")
        return {"error": True, "message": str(exc)}"""
CALC_NEW = """def _tool_nutri_meal_calc(meal_description: str, **kwargs) -> dict:
    try:
        from nutrition.services import calculate_meal
        return calculate_meal(meal_description)
    except ImportError:
        return {
            "error": True,
            "tool_failed": True,
            "service": "nutrition",
            "message": "TOOL_FAILURE: nutrition service is unavailable. "
                       "Do not provide any alternative information. "
                       "Tell the user the service is temporarily unavailable "
                       "and suggest they try injury risk or player search instead.",
        }
    except Exception as exc:
        logger.exception("nutri_meal_calc failed")
        return {"error": True, "message": str(exc)}"""
tools_text = tools_text.replace(CALC_OLD, CALC_NEW)


# Bug 1 part 3: Fix food_search mock return
FOOD_OLD = """def _tool_food_search(query: str, limit: int = 5, **kwargs) -> dict:
    try:
        from nutrition.services import search_food_database
        limit = min(max(1, int(limit)), 20)
        return search_food_database(query, limit)
    except ImportError:
        return {"error": True, "message": "Food database not available."}
    except Exception as exc:
        logger.exception("food_search failed for '%s'", query)
        return {"error": True, "message": str(exc)}"""
FOOD_NEW = """def _tool_food_search(query: str, limit: int = 5, **kwargs) -> dict:
    try:
        from nutrition.services import search_food_database
        limit = min(max(1, int(limit)), 20)
        return search_food_database(query, limit)
    except ImportError:
        return {
            "error": True,
            "tool_failed": True,
            "service": "nutrition",
            "message": "TOOL_FAILURE: nutrition service is unavailable. "
                       "Do not provide any alternative information. "
                       "Tell the user the service is temporarily unavailable "
                       "and suggest they try injury risk or player search instead.",
        }
    except Exception as exc:
        logger.exception("food_search failed for '%s'", query)
        return {"error": True, "message": str(exc)}"""
tools_text = tools_text.replace(FOOD_OLD, FOOD_NEW)

with codecs.open(tools_path, 'w', 'utf-8') as f:
    f.write(tools_text)

print("Files patched.")