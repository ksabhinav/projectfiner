<script>
  import { onMount, tick } from 'svelte';

  let question = $state('');
  let loading = $state(false);
  let messages = $state([]);
  let inputEl;
  let messagesEl;

  const API_URL = 'https://projectfiner-api.vercel.app/api/ask';

  function md(text) {
    if (!text) return '';
    return text
      .replace(/^### (.+)$/gm, '<h4>$1</h4>')
      .replace(/^## (.+)$/gm, '<h3>$1</h3>')
      .replace(/^# (.+)$/gm, '<h3>$1</h3>')
      .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
      .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
      .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
      .replace(/\n{2,}/g, '</p><p>')
      .replace(/\n/g, '<br>')
      .replace(/^/, '<p>')
      .replace(/$/, '</p>')
      .replace(/<p><(h[34]|ul)/g, '<$1')
      .replace(/<\/(h[34]|ul)><\/p>/g, '</$1>')
      .replace(/<p><\/p>/g, '');
  }

  const SUGGESTIONS = [
    'KCC cards in Meghalaya by district?',
    'CD ratio of Bihar districts?',
    'Branch network in Manipur rural areas?',
    'PMJDY accounts in Assam?',
  ];

  async function scrollToBottom() {
    await tick();
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  async function submit() {
    const q = question.trim();
    if (!q || loading) return;

    messages = [...messages, { role: 'user', text: q }];
    question = '';
    loading = true;
    scrollToBottom();

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
      messages = [...messages, { role: 'error', text: 'Network error. Please try again.' }];
    } finally {
      loading = false;
      scrollToBottom();
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

<div class="chat">
  <!-- Messages area -->
  <div class="thread" bind:this={messagesEl}>
    {#if messages.length === 0}
      <div class="empty-state">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <p class="empty-title">Ask anything about SLBC data</p>
        <p class="empty-sub">District-level financial data across 16 states. Try:</p>
        <div class="pills">
          {#each SUGGESTIONS as s}
            <button class="pill" onclick={() => useSuggestion(s)}>{s}</button>
          {/each}
        </div>
      </div>
    {:else}
      {#each messages as msg}
        {#if msg.role === 'user'}
          <div class="bubble-row user-row">
            <div class="bubble user-bubble">{msg.text}</div>
          </div>
        {:else if msg.role === 'assistant'}
          <div class="bubble-row ai-row">
            <div class="avatar">F</div>
            <div class="bubble ai-bubble">
              <div class="ai-text prose">{@html md(msg.text)}</div>
              {#if msg.sources?.length}
                <div class="src-bar">
                  {#each msg.sources as src}
                    <span class="src-tag" title={src.snippet}>
                      {src.state} · {src.type} · {src.quarter}
                    </span>
                  {/each}
                </div>
              {/if}
            </div>
          </div>
        {:else}
          <div class="bubble-row ai-row">
            <div class="avatar err-avatar">!</div>
            <div class="bubble err-bubble">{msg.text}</div>
          </div>
        {/if}
      {/each}

      {#if loading}
        <div class="bubble-row ai-row">
          <div class="avatar">F</div>
          <div class="bubble ai-bubble">
            <div class="typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      {/if}
    {/if}
  </div>

  <!-- Input bar -->
  <form class="composer" onsubmit={(e) => { e.preventDefault(); submit(); }}>
    <input
      bind:this={inputEl}
      bind:value={question}
      onkeydown={handleKeydown}
      placeholder="Message..."
      disabled={loading}
      maxlength="500"
    />
    <button type="submit" class="send-btn" disabled={loading || !question.trim()} aria-label="Send">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="22" y1="2" x2="11" y2="13"/>
        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
      </svg>
    </button>
  </form>
</div>

<style>
  .chat {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 200px);
    min-height: 480px;
    max-height: 800px;
  }

  /* ── Thread ── */
  .thread {
    flex: 1;
    overflow-y: auto;
    padding: 16px 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    scroll-behavior: smooth;
  }
  .thread::-webkit-scrollbar { width: 4px; }
  .thread::-webkit-scrollbar-thumb { background: #ddd; border-radius: 4px; }

  /* ── Empty state ── */
  .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 40px 20px;
  }
  .empty-icon {
    color: var(--label, #aaa09a);
    margin-bottom: 4px;
  }
  .empty-title {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 16px;
    font-weight: 600;
    color: var(--text, #1a1410);
    margin: 0;
  }
  .empty-sub {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 13px;
    color: var(--muted, #888078);
    margin: 0 0 12px;
  }
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    max-width: 480px;
  }
  .pill {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 12px;
    color: var(--text, #1a1410);
    background: #fff;
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 18px;
    padding: 7px 14px;
    cursor: pointer;
    transition: all 0.15s;
    line-height: 1.3;
  }
  .pill:hover {
    background: var(--text, #1a1410);
    color: #fff;
    border-color: var(--text, #1a1410);
  }

  /* ── Bubbles ── */
  .bubble-row {
    display: flex;
    gap: 8px;
    padding: 4px 0;
    max-width: 100%;
  }
  .user-row {
    justify-content: flex-end;
  }
  .ai-row {
    justify-content: flex-start;
    align-items: flex-start;
  }

  .avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--text, #1a1410);
    color: #fff;
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 11px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .err-avatar {
    background: #c44830;
  }

  .bubble {
    max-width: 85%;
    padding: 10px 14px;
    border-radius: 18px;
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 14px;
    line-height: 1.55;
    word-wrap: break-word;
  }

  .user-bubble {
    background: var(--text, #1a1410);
    color: #fff;
    border-bottom-right-radius: 4px;
  }

  .ai-bubble {
    background: #fff;
    color: var(--text, #1a1410);
    border: 1px solid var(--border, #e8e5e0);
    border-bottom-left-radius: 4px;
  }

  .err-bubble {
    background: #fef2f2;
    color: #c44830;
    border: 1px solid #fecaca;
    border-bottom-left-radius: 4px;
    font-size: 13px;
  }

  /* ── AI prose ── */
  .ai-text.prose {
    white-space: normal;
  }
  .ai-text.prose :global(h3) {
    font-size: 15px;
    font-weight: 700;
    color: var(--text, #1a1410);
    margin: 14px 0 6px;
  }
  .ai-text.prose :global(h3:first-child) {
    margin-top: 0;
  }
  .ai-text.prose :global(h4) {
    font-size: 14px;
    font-weight: 700;
    margin: 10px 0 4px;
  }
  .ai-text.prose :global(strong) {
    font-weight: 700;
  }
  .ai-text.prose :global(em) {
    font-style: italic;
    color: var(--muted, #888078);
  }
  .ai-text.prose :global(p) {
    margin: 0 0 8px;
  }
  .ai-text.prose :global(p:last-child) {
    margin-bottom: 0;
  }
  .ai-text.prose :global(ul) {
    margin: 6px 0 10px;
    padding-left: 18px;
    list-style: none;
  }
  .ai-text.prose :global(li) {
    position: relative;
    padding-left: 2px;
    margin-bottom: 3px;
  }
  .ai-text.prose :global(li::before) {
    content: '';
    position: absolute;
    left: -12px;
    top: 8px;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: var(--accent, #b8603e);
  }

  /* ── Sources ── */
  .src-bar {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px solid rgba(0,0,0,0.06);
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .src-tag {
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 10px;
    color: var(--muted, #888078);
    background: rgba(0,0,0,0.03);
    border-radius: 10px;
    padding: 3px 8px;
    cursor: default;
    transition: color 0.15s;
  }
  .src-tag:hover {
    color: var(--text, #1a1410);
  }

  /* ── Typing indicator ── */
  .typing {
    display: flex;
    gap: 4px;
    padding: 4px 0;
  }
  .typing span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--label, #aaa09a);
    animation: bounce 1.4s infinite ease-in-out;
  }
  .typing span:nth-child(2) { animation-delay: 0.16s; }
  .typing span:nth-child(3) { animation-delay: 0.32s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
  }

  /* ── Composer ── */
  .composer {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 0 4px;
    border-top: 1px solid var(--border, #e8e5e0);
    background: var(--bg, #f5f4f1);
  }
  .composer input {
    flex: 1;
    font-family: var(--font-sans, Inter, sans-serif);
    font-size: 14px;
    padding: 12px 16px;
    border: 1px solid var(--border, #e8e5e0);
    border-radius: 24px;
    background: #fff;
    color: var(--text, #1a1410);
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .composer input:focus {
    border-color: var(--text, #1a1410);
    box-shadow: 0 0 0 3px rgba(26,20,16,0.06);
  }
  .composer input::placeholder {
    color: var(--label, #aaa09a);
  }

  .send-btn {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: none;
    background: var(--text, #1a1410);
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: all 0.15s;
  }
  .send-btn:hover:not(:disabled) {
    background: var(--accent, #b8603e);
    transform: scale(1.05);
  }
  .send-btn:disabled {
    opacity: 0.25;
    cursor: not-allowed;
  }

  @media (max-width: 640px) {
    .chat { height: calc(100vh - 180px); min-height: 400px; }
    .bubble { max-width: 92%; font-size: 13px; }
    .pill { font-size: 11px; padding: 6px 12px; }
    .composer input { padding: 10px 14px; font-size: 13px; }
  }
</style>
