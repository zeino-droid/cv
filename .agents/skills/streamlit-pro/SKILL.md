# Streamlit Expert Skill

## Description
You are an expert in building high-performance, responsive, and robust web applications using Streamlit. You understand the nuances of Streamlit's execution model and know how to avoid common pitfalls like unnecessary reruns and state loss.

## Best Practices & Rules

### 1. State Management
- **ALWAYS** use `st.session_state` to store user inputs, API responses, or intermediate computations that need to survive a script rerun.
- Initialize default values in `st.session_state` at the very beginning of your script to prevent `KeyError`.

### 2. Caching
- Use `@st.cache_data` for functions that return serializable data (e.g., pandas DataFrames, API responses, JSON).
- Use `@st.cache_resource` for functions that return global resources (e.g., database connections, ML models).
- Always consider the `show_spinner` argument and mutation behavior when caching.

### 3. Callbacks over Reruns
- When interacting with buttons or inputs that update state, prefer using `on_change` or `on_click` callbacks instead of handling the logic sequentially. This ensures the state is updated *before* the rest of the script reruns.

### 4. UI/UX and Layout
- Use `st.columns()` and `st.container()` to organize the layout cleanly.
- Keep the UI responsive and avoid dumping too much text directly without formatting.
- Make use of `st.expander` to hide less critical information and declutter the UI.
- Apply custom CSS via `st.markdown("<style>...</style>", unsafe_allow_html=True)` only when absolutely necessary for premium aesthetics, as Streamlit's native components are preferred.

### 5. Decoupling Logic
- NEVER write business logic directly inside the UI rendering code.
- Write pure Python functions for processing (which can be tested independently) and import them into your Streamlit dashboard.

### 6. Performance
- Avoid large loops or heavy computations directly in the main thread without caching.
- If performing long-running tasks, use `st.spinner()` or `st.status()` to provide immediate feedback to the user.

## Example Project Structure
```python
# Initialization
if "user_data" not in st.session_state:
    st.session_state.user_data = None

# Logic
@st.cache_data
def fetch_data(query):
    return backend.fetch(query)

# UI
st.title("My Dashboard")
query = st.text_input("Search")
if st.button("Run"):
    with st.spinner("Fetching..."):
         st.session_state.user_data = fetch_data(query)

if st.session_state.user_data:
    st.write(st.session_state.user_data)
```
