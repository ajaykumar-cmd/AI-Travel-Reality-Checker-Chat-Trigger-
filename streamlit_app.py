import streamlit as st
from groq import Groq
import json

# ============================================
# CONFIG
# ============================================
st.set_page_config(page_title="AI Travel Reality Checker", page_icon="🌍", layout="centered")

MODEL = "openai/gpt-oss-120b"

# Get Groq API key from Streamlit secrets or user input
def get_client():
    api_key = st.session_state.get("groq_api_key", "")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def call_agent(client, system_prompt, user_prompt, json_mode=False):
    """Call a single agent with a system + user prompt. Returns text or parsed JSON."""
    kwargs = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content

    if json_mode:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # fallback: try to extract JSON block
            start = content.find("{")
            end = content.rfind("}") + 1
            return json.loads(content[start:end])
    return content


# ============================================
# AGENT DEFINITIONS
# ============================================

def agent_reality_checker(client, destination, budget, currency, num_days, num_travelers, travel_style):
    system_prompt = """You are a travel budget analyst. Analyze the given destination, days, travelers, and budget against realistic average costs (flights/transport, hotels, food, local transport, activities). Always respond ONLY in valid JSON, in this exact format:
{
  "verdict": "REALISTIC | TIGHT | UNREALISTIC",
  "budget_gap_percent": number,
  "estimated_total_cost": number,
  "cost_breakdown": {
    "flights": number,
    "hotels": number,
    "food": number,
    "local_transport": number,
    "activities": number
  },
  "reasoning": "short explanation"
}"""
    user_prompt = f"""Destination: {destination}
Budget: {budget} {currency}
Days: {num_days}
Travelers: {num_travelers}
Travel Style: {travel_style}

Evaluate if this budget is REALISTIC, TIGHT, or UNREALISTIC for the given days and travelers."""
    return call_agent(client, system_prompt, user_prompt, json_mode=True)


def agent_optimizer(client, trip_data, reality_check):
    system_prompt = """You are a travel itinerary optimizer. Given the budget analysis, cost breakdown, and gap, suggest specific money-saving swaps and adjustments so the trip fits the budget while staying enjoyable. Be concrete and destination-specific. Output plain text with clear bullet points grouped under: Accommodation, Transport, Food, Activities."""
    user_prompt = f"""Destination: {trip_data['destination']}
Days: {trip_data['num_days']}
Travelers: {trip_data['num_travelers']}
Budget: {trip_data['budget']} {trip_data['currency']}
Verdict: {reality_check['verdict']}
Budget Gap %: {reality_check['budget_gap_percent']}
Cost Breakdown: {json.dumps(reality_check['cost_breakdown'])}
Reasoning: {reality_check['reasoning']}

Suggest specific, practical optimizations to fit the budget."""
    return call_agent(client, system_prompt, user_prompt, json_mode=False)


def agent_final_plan(client, trip_data, reality_check, optimizations):
    system_prompt = """You are a professional travel planner. Produce a polished FINAL travel plan in Markdown with:
1. A short summary (budget verdict + final adjusted budget)
2. Day-wise itinerary (Day 1, Day 2, ...) with morning/afternoon/evening activities
3. Updated cost breakdown table after optimizations
4. Practical tips & warnings section
Keep it clear, well-formatted, and realistic."""
    user_prompt = f"""Destination: {trip_data['destination']}
Days: {trip_data['num_days']}
Travelers: {trip_data['num_travelers']}
Budget: {trip_data['budget']} {trip_data['currency']}
Travel Style: {trip_data['travel_style']}
Reality Check Verdict: {reality_check['verdict']}
Cost Breakdown: {json.dumps(reality_check['cost_breakdown'])}
Optimizations Suggested: {optimizations}"""
    return call_agent(client, system_prompt, user_prompt, json_mode=False)


# ============================================
# UI
# ============================================

st.title("🌍 AI Travel Reality Checker")
st.markdown("Multi-agent system: **Reality Checker → Optimizer → Final Plan Generator**")

with st.sidebar:
    st.header("🔑 Groq API Key")
    api_key_input = st.text_input("Enter your Groq API key", type="password", value=st.session_state.get("groq_api_key", ""))
    if api_key_input:
        st.session_state["groq_api_key"] = api_key_input
        st.success("API key set ✅")

with st.form("trip_form"):
    col1, col2 = st.columns(2)
    with col1:
        destination = st.text_input("Destination", placeholder="e.g. Goa")
        budget = st.number_input("Budget", min_value=0, step=500, value=25000)
        currency = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP"])
    with col2:
        num_days = st.number_input("Number of Days", min_value=1, max_value=30, value=4)
        num_travelers = st.number_input("Number of Travelers", min_value=1, max_value=20, value=2)
        travel_style = st.selectbox("Travel Style", ["budget", "mid-range", "luxury"])

    submitted = st.form_submit_button("Check My Trip ✈️")

if submitted:
    client = get_client()
    if not client:
        st.error("Please enter your Groq API key in the sidebar first.")
    elif not destination:
        st.error("Please enter a destination.")
    else:
        trip_data = {
            "destination": destination,
            "budget": budget,
            "currency": currency,
            "num_days": num_days,
            "num_travelers": num_travelers,
            "travel_style": travel_style,
        }

        try:
            # Agent 1: Reality Checker
            with st.status("🕵️ Agent 1: Checking budget reality...", expanded=False) as status:
                reality_check = agent_reality_checker(client, **trip_data)
                status.update(label=f"✅ Reality Check: {reality_check['verdict']}", state="complete")

            with st.expander("📊 Reality Check Details"):
                st.json(reality_check)

            if reality_check["verdict"] == "UNREALISTIC":
                st.error(
                    f"⚠️ Your budget of {budget} {currency} is **UNREALISTIC** for {destination} "
                    f"for {num_days} days.\n\n"
                    f"**Gap:** {reality_check['budget_gap_percent']}%\n\n"
                    f"**Estimated real cost:** {reality_check['estimated_total_cost']} {currency}\n\n"
                    f"**Reasoning:** {reality_check['reasoning']}\n\n"
                    f"Please increase your budget or reduce trip duration and try again."
                )
            else:
                # Agent 2: Optimizer
                with st.status("🛠️ Agent 2: Optimizing itinerary...", expanded=False) as status:
                    optimizations = agent_optimizer(client, trip_data, reality_check)
                    status.update(label="✅ Optimizations ready", state="complete")

                with st.expander("💡 Optimization Suggestions"):
                    st.markdown(optimizations)

                # Agent 3: Final Plan Generator
                with st.status("📝 Agent 3: Building final plan...", expanded=False) as status:
                    final_plan = agent_final_plan(client, trip_data, reality_check, optimizations)
                    status.update(label="✅ Final plan ready", state="complete")

                st.success("Here's your travel plan!")
                st.markdown(final_plan)

        except Exception as e:
            st.error(f"Something went wrong: {e}")

st.markdown("---")
st.caption("Multi-Agent AI System · Powered by Groq (gpt-oss-120b)")
