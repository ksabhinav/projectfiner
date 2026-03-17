<script>
  import { onMount } from 'svelte';

  let question = $state('');
  let loading = $state(false);
  let messages = $state([]);
  let inputEl;

  const API_URL = '/api/ask';

  const SUGGESTIONS = [
    'What KCC targets were set for Assam in 2024?',
    'How has the CD ratio changed in Meghalaya?',
    'What digital transaction initiatives were discussed in Manipur?',
    'What are the key financial inclusion challenges in Nagaland?',
  ];

  async function submit() {
    const q = question.trim();
    if (!q || loading) return;

    messages = [...messages, { role: 'user', text: q }];
    question = '';
    loading = true;

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Server error' }));
        messages = [...messages, { role: 'error', text: err.error || 'Something went wrong.' }];
        return;
      }

      const data = await res.json();
      messages = [...messages, { role: 'assistant', text: data.answer, sources: data.sources }];
    } catch (e) {
      messages = [...messages, { role: 'error', text: 'Network error. Make sure the API is deployed.' }];
    } finally {
      loading = false;
    }
  }

  function useSuggestion(s) {
    question = s;
    submit();
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  onMount(() => {
    inputEl?.focus();
  });
</script>

<div class="chat-container">
  {#if messages.length === 0}
    <div class="welcome">
      <p class="welcome-text">Ask any question about SLBC NE meeting documents — booklets, minutes, policy discussions, targets, and performance reviews across Assam, Meghalaya, Manipur, Mizoram, Nagaland, and Arunachal Pradesh.</p>
      <div class="suggestions">
        {#each SUGGESTIONS as s}
          <button class="suggestion" onclick={() => useSuggestion(s)}>{s}</button>
        {/each}
      </div>
    </div>
  {/if}

  <div class="messages">
    {#each messages as msg}
      <div class="message {msg.role}">
        {#if msg.role === 'user'}
          <div class="msg-label">You</div>
          <div class="msg-text">{msg.text}</div>
        {:else if msg.role === 'assistant'}
          <div class="msg-label">FINER</div>
          <div class="msg-text">{msg.text}</div>
          {#if msg.sources?.length}
            <div class="sources">
              <div class="sources-label">Sources</div>
              <div class="source-chips">
                {#each msg.sources as src}
                  <span class="source-chip" title={src.snippet}>
                    {src.state} &middot; {src.type} &middot; {src.quarter}
                  </span>
                {/each}
              </div>
            </div>
          {/if}
        {:else}
          <div class="msg-label">Error</div>
          <div class="msg-text error-text">{msg.text}</div>
        {/if}
      </div>
    {/each}

    {#if loading}
      <div class="message assistant">
        <div class="msg-label">FINER</div>
        <div class="msg-text loading-dots">Searching documents<span class="dots"></span></div>
      </div>
    {/if}
  </div>

  <form class="input-area" onsubmit={(e) => { e.preventDefault(); submit(); }}>
    <input
      bind:this={inputEl}
      bind:value={question}
      onkeydown={handleKeydown}
      placeholder="Ask about SLBC NE meetings..."
      disabled={loading}
      maxlength="500"
    />
    <button type="submit" disabled={loading || !question.trim()}>
      {loading ? '...' : 'Ask'}
    </button>
  </form>
</div>

<style>
  .chat-container {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }

  /* Welcome */
  .welcome {
    text-align: center;
    padding: 32px 0 16px;
  }
  .welcome-text {
    font-family: Georgia, serif;
    font-size: 14px;
    color: var(--muted, #888078);
    line-height: 1.7;
    max-width: 560px;
    margin: 0 auto 24px;
  }
  .suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }
  .suggestion {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 11px;
    color: var(--text, #1a1410);
    background: #fff;
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 20px;
    padding: 8px 16px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .suggestion:hover {
    border-color: var(--accent, #b8603e);
    color: var(--accent, #b8603e);
  }

  /* Messages */
  .messages {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .message {
    padding: 16px 20px;
    border-radius: 10px;
    border: 1px solid var(--border, #e8e5e0);
    background: #fff;
  }
  .message.user {
    background: rgba(245, 244, 241, 0.6);
    border-left: 3px solid var(--muted, #888078);
  }
  .message.assistant {
    border-left: 3px solid var(--accent, #b8603e);
  }
  .message.error {
    border-left: 3px solid #c44830;
  }

  .msg-label {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--label, #aaa09a);
    margin-bottom: 8px;
  }
  .msg-text {
    font-family: Georgia, serif;
    font-size: 14px;
    line-height: 1.7;
    color: var(--text, #1a1410);
    white-space: pre-wrap;
  }
  .error-text {
    color: #c44830;
  }

  /* Sources */
  .sources {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--border, #e8e5e0);
  }
  .sources-label {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--label, #aaa09a);
    margin-bottom: 8px;
  }
  .source-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .source-chip {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--muted, #888078);
    background: rgba(245, 244, 241, 0.8);
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 4px;
    padding: 4px 8px;
    cursor: default;
  }
  .source-chip:hover {
    color: var(--text, #1a1410);
    border-color: var(--accent, #b8603e);
  }

  /* Loading dots */
  .loading-dots .dots::after {
    content: '';
    animation: dots 1.2s steps(4, end) infinite;
  }
  @keyframes dots {
    0% { content: ''; }
    25% { content: '.'; }
    50% { content: '..'; }
    75% { content: '...'; }
  }

  /* Input area */
  .input-area {
    display: flex;
    gap: 8px;
    position: sticky;
    bottom: 20px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    padding: 12px;
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 12px;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.04);
  }
  .input-area input {
    flex: 1;
    font-family: Georgia, serif;
    font-size: 14px;
    padding: 10px 14px;
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 8px;
    background: #fff;
    color: var(--text, #1a1410);
    outline: none;
    transition: border-color 0.2s;
  }
  .input-area input:focus {
    border-color: var(--accent, #b8603e);
  }
  .input-area input::placeholder {
    color: var(--label, #aaa09a);
  }
  .input-area button {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 10px 20px;
    border: 1px solid var(--text, #1a1410);
    border-radius: 8px;
    background: var(--text, #1a1410);
    color: #fff;
    cursor: pointer;
    transition: all 0.2s;
  }
  .input-area button:hover:not(:disabled) {
    background: var(--accent, #b8603e);
    border-color: var(--accent, #b8603e);
  }
  .input-area button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  @media (max-width: 768px) {
    .suggestion {
      font-size: 10px;
      padding: 6px 12px;
    }
    .input-area {
      bottom: 10px;
      padding: 8px;
    }
  }
</style>
