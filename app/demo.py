"""Deadline Radar live demo: one input through the whole pipeline, every step on screen.

    pip install -e ".[demo,rag]"
    streamlit run app/demo.py

Live mode calls the model (2 to 3 calls per run). Replay mode shows a saved live run of the same example and says
so on screen; use it only if the network fails.
"""

import time

import pandas as pd
import streamlit as st

from aic390 import demo
from aic390.agent.searchlog import model_calls
from aic390.llm import OpenAICompatibleClient

st.set_page_config(page_title="Deadline Radar", layout="wide")


@st.cache_resource(show_spinner="Loading the search index...")
def cached_search(kind: str):
    start = time.perf_counter()
    search = demo.make_search(kind)
    return search, time.perf_counter() - start


@st.cache_resource
def cached_client():
    return OpenAICompatibleClient()


def backend_available(kind: str) -> bool:
    if kind == "stub":
        return True
    try:
        import bm25s  # noqa: F401

        if kind == "hybrid":
            import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


# Sidebar: how the run is set up --------------------------------------------------------------------------------

st.sidebar.title("Run settings")
mode = st.sidebar.radio("Mode", ["Live", "Replay (saved live run)"], index=0)
# Replay needs no search engine, so every backend can be replayed on any computer.
kinds = [k for k in demo.SEARCH_BACKENDS if mode != "Live" or backend_available(k)]
search_kind = st.sidebar.selectbox(
    "Search backend",
    kinds,
    index=len(kinds) - 1,
    format_func=lambda k: demo.SEARCH_BACKENDS[k],
)
extract_version = st.sidebar.selectbox("Extraction prompt", ["extract_v1", "extract_v2", "extract_v3"])
answer_version = st.sidebar.selectbox(
    "Answer prompt",
    ["answer_v1", "answer_v2"],
    help="default answer_v1 (Run B rule, STATUS); answer_v2 (W3.4): [n] citations and fixed abstentions",
)
if mode == "Live":
    st.sidebar.caption(f"Search index ready in {cached_search(search_kind)[1]:.1f} s (loaded once).")
st.sidebar.caption("Model: openai/gpt-oss-120b on Groq, temperature 0. Deadline table: data/db/deadlines_seed.jsonl.")

# Input ---------------------------------------------------------------------------------------------------------

st.title("Deadline Radar")
st.caption("Classifier → route → extraction or retrieval → answer. The model reads; dates, trust and counts are code.")

titles = {e["id"]: e["title"] for e in demo.EXAMPLES}
example_id = st.selectbox("Example", ["(write your own)", *titles], format_func=lambda i: titles.get(i, i))
base = next((e["case"] for e in demo.EXAMPLES if e["id"] == example_id), None) or {
    "channel": "chat",
    "received_at": "2026-11-19T20:00:00+03:00",
    "course": None,
    "sender": "user",
    "text": "",
}

c1, c2, c3, c4 = st.columns(4)
channels = ["email", "lms", "chat"]
channel = c1.selectbox("Channel", channels, index=channels.index(base["channel"]), key=f"ch-{example_id}")
sender = c2.text_input("Sender (from metadata)", base["sender"], key=f"se-{example_id}")
course = c3.text_input("Course", base["course"] or "", key=f"co-{example_id}")
received_at = c4.text_input("Received at", base["received_at"], key=f"ra-{example_id}")
text = st.text_area("Message or question", base["text"], height=140, key=f"tx-{example_id}")
case = {
    "id": example_id,
    "channel": channel,
    "received_at": received_at,
    "course": course or None,
    "sender": sender,
    "text": text,
}

if st.button("Run", type="primary", disabled=not text.strip()):
    if mode == "Live":
        try:
            with st.spinner("Running the pipeline..."):
                record = demo.run_demo(
                    case,
                    cached_client(),
                    search_kind,
                    cached_search(search_kind)[0],
                    prompts={"extract": extract_version, "answer": answer_version},
                )
            if example_id in titles:
                demo.save_replay(record, example_id)
            st.session_state["record"] = record
        except Exception as exc:  # shown, never hidden: switch to replay if the network is down
            st.error(f"Live run failed: {exc!r}. Switch to Replay to show a saved run.")
    else:
        record = demo.load_replay(example_id, search_kind)
        if record is None:
            st.warning("No saved live run of this example with this search backend.")
        st.session_state["record"] = record

record = st.session_state.get("record")
if not record:
    st.stop()

out = record["output"]
if record["mode"] == "replay":
    used = [t["prompt_version"] for t in model_calls(out["trace"])]
    chunks = record.get("n_chunks") or "an earlier, smaller number of"
    st.warning(
        f"REPLAY of a live run from {record['ran_at']}, {chunks} chunks searched, "
        f"{', '.join(used)} (not a new model call)."
    )

# 1. Classifier -------------------------------------------------------------------------------------------------

st.subheader("1 · Classifier")
cls = out["classifier"]
st.markdown(
    f"**Intent** `{cls['intent']}` · **Course** `{cls['course'] or 'none'}` · **Urgency** `{cls['urgency']}` · "
    f"**Several requests** `{'yes' if cls['multi_step'] else 'no'}`"
)

# 2. Route ------------------------------------------------------------------------------------------------------

st.subheader("2 · Route (code)")
st.info(record["route"])

# 3. Extraction or retrieval ------------------------------------------------------------------------------------

st.subheader("3 · Extraction, retrieval and checks")
if out["untrusted_flag"]:
    st.error(f"Sender '{record['case']['sender']}' may not change deadlines: nothing changed, the model was not asked.")
if out["deadlines"]:
    st.dataframe(pd.DataFrame(out["deadlines"]), hide_index=True, width="stretch")
if out["ask_user"]:
    st.warning("Two readings change the answer: the student is asked before anything is saved.")
for call in record["retrieved"]:
    st.markdown(
        f"**Search** `{call['query']}` · course `{call['course']}` · type `{call['doc_type']}` · "
        f"as of `{call['as_of']}` · {len(call['hits'])} hits"
    )
    if call["hits"]:
        hits = pd.DataFrame(call["hits"])[
            ["doc_id", "section", "score", "bm25_rank", "dense_rank", "rerank_score", "text"]
        ]
        st.dataframe(hits, hide_index=True, width="stretch")
if out["sources"]:
    st.markdown("**Cited:** " + "; ".join(f"`{s['doc_id']}` · {s['section']}" for s in out["sources"]))

# 4. Answer -----------------------------------------------------------------------------------------------------

st.subheader("4 · Answer")
if not out["valid"]:
    st.error("A model reply was not valid JSON after one retry (see the trace): nothing was saved.")
if out["abstain"]:
    st.caption("Abstained: no answer is given without a source.")
st.success(out["answer_text"] or "(no reply)")
if out["count"] is not None:
    st.metric("Count (from the table, not the model)", out["count"])
if out["action"]:
    a = out["action"]
    st.markdown(f"**Reminder preview:** {a['remind_at']} · waiting for confirmation")
    if st.button("Confirm reminder"):
        st.caption("Nothing is written: the reminder write action is the week-5 sandbox task.")

# 5. Trace ------------------------------------------------------------------------------------------------------

st.subheader("5 · Trace")
calls = pd.DataFrame(model_calls(out["trace"]))
searches = [t for t in out["trace"] if t["step"] == "search"]
if not calls.empty:
    st.dataframe(calls, hide_index=True, width="stretch")
    st.caption(
        f"{len(calls)} model calls · {int(calls['input_tokens'].sum())} input and "
        f"{int(calls['output_tokens'].sum())} output tokens · {calls['latency_s'].sum():.1f} s in the model"
    )
if searches:
    st.caption(f"{len(searches)} search calls · {sum(t['latency_s'] for t in searches):.2f} s in search")
with st.expander("Deadline table as it stood at received_at"):
    st.dataframe(pd.DataFrame(record["table_at_received"]), hide_index=True, width="stretch")
