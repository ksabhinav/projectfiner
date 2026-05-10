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

  // On mobile, show only 2 pills to save space
  let isMobile = $state(false);
  onMount(() => {
    isMobile = window.innerWidth <= 640;
  });
  let visibleSuggestions = $derived(isMobile ? SUGGESTIONS.slice(0, 2) : SUGGESTIONS);

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
          {#each visibleSuggestions as s}
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
  /* ── Atlas /ask treatment ── */
  .chat {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  /* Thread */
  .thread {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: 8px 0;
    display: flex;
    flex-direction: column;
    gap: 18px;
    scroll-behavior: smooth;
  }
  .thread::-webkit-scrollbar { width: 4px; }
  .thread::-webkit-scrollbar-thumb { background: var(--rule, #D9D2C5); border-radius: 4px; }

  /* Empty state — hug top so pills sit right below the hero */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
    padding: 10px 0 0;
  }
  .empty-icon { display: none; }
  .empty-title {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 22px;
    letter-spacing: -0.01em;
    color: var(--ink, #1B140E);
    margin: 0;
  }
  .empty-sub {
    font-family: 'Source Serif 4', Georgia, serif;
    font-style: italic;
    font-size: 14px;
    color: var(--mist, #6E665E);
    margin: 0 0 6px;
  }
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    max-width: 720px;
  }
  .pill {
    font-family: 'Source Serif 4', Georgia, serif;
    font-style: italic;
    font-size: 13px;
    color: var(--ink-soft, #3D332A);
    background: var(--paper, #F4EFE6);
    border: 1px solid var(--rule, #D9D2C5);
    border-radius: 99px;
    padding: 7px 13px;
    cursor: pointer;
    transition: border-color 160ms ease, background 160ms ease;
    line-height: 1.3;
  }
  .pill:hover {
    background: var(--paper-deep, #ECE5D6);
    border-color: var(--vermillion, #B84A2E);
    color: var(--ink, #1B140E);
  }

  /* Bubble rows */
  .bubble-row {
    display: flex;
    gap: 10px;
    max-width: 100%;
  }
  .user-row { justify-content: flex-end; }
  .ai-row {
    justify-content: flex-start;
    align-items: flex-start;
    flex-direction: column;
  }

  /* User: ink bubble, paper text, asymmetric radius (Atlas) */
  .bubble.user-bubble {
    align-self: flex-end;
    max-width: 75%;
    padding: 12px 18px;
    background: var(--ink, #1B140E);
    color: var(--paper, #F4EFE6);
    border-radius: 16px 16px 4px 16px;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 15px;
    line-height: 1.5;
    word-wrap: break-word;
  }

  /* Bot: full-width with vermillion "FINER · finding" eyebrow */
  .ai-row .avatar { display: none; } /* drop the F avatar */
  .bubble.ai-bubble {
    max-width: 100%;
    padding: 6px 0;
    background: transparent;
    border: 0;
    border-radius: 0;
    position: relative;
  }
  .bubble.ai-bubble::before {
    content: 'FINER · finding';
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--vermillion, #B84A2E);
    margin-bottom: 10px;
  }
  .bubble.ai-bubble::after {
    content: '';
    position: absolute;
    top: 5px;
    left: 110px;
    right: 0;
    height: 1px;
    background: var(--rule, #D9D2C5);
  }

  /* Error: burgundy treatment */
  .err-bubble {
    align-self: flex-start;
    max-width: 80%;
    padding: 12px 18px;
    background: rgba(140, 46, 32, 0.08);
    color: var(--burgundy, #8C2E20);
    border-left: 3px solid var(--burgundy, #8C2E20);
    border-radius: 4px;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 14px;
    line-height: 1.5;
  }
  .err-avatar { display: none; }

  /* AI prose */
  .ai-text.prose {
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 16px;
    line-height: 1.65;
    color: var(--ink, #1B140E);
    margin-bottom: 14px;
  }
  .ai-text.prose :global(h3) {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 400;
    font-variation-settings: 'opsz' 60;
    font-size: 19px;
    color: var(--ink, #1B140E);
    margin: 18px 0 8px;
    letter-spacing: -0.005em;
  }
  .ai-text.prose :global(h3:first-child) { margin-top: 0; }
  .ai-text.prose :global(h4) {
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--vermillion, #B84A2E);
    margin: 14px 0 6px;
  }
  .ai-text.prose :global(strong) {
    font-family: 'Fraunces', Georgia, serif;
    font-weight: 500;
    color: var(--ink, #1B140E);
  }
  .ai-text.prose :global(em) {
    font-style: italic;
    color: var(--vermillion-d, #8E331E);
  }
  .ai-text.prose :global(p) { margin: 0 0 12px; }
  .ai-text.prose :global(p:last-child) { margin-bottom: 0; }
  .ai-text.prose :global(ul) {
    margin: 8px 0 12px;
    padding-left: 20px;
    list-style: none;
  }
  .ai-text.prose :global(li) {
    position: relative;
    padding-left: 4px;
    margin-bottom: 6px;
  }
  .ai-text.prose :global(li::before) {
    content: '';
    position: absolute;
    left: -14px;
    top: 10px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--vermillion, #B84A2E);
  }

  /* Sources — peacock mono chips on paper-deep capsules */
  .src-bar {
    margin-top: 14px;
    padding-top: 12px;
    border-top: 1px solid var(--rule-soft, #E8E2D5);
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .src-bar::before {
    content: 'Sources';
    font-family: 'Inter', sans-serif;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--mist, #6E665E);
    width: 100%;
    margin-bottom: 6px;
  }
  .src-tag {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--peacock, #1E4960);
    background: var(--paper-deep, #ECE5D6);
    border: 1px solid var(--rule, #D9D2C5);
    border-radius: 99px;
    padding: 4px 10px;
    cursor: default;
    letter-spacing: 0.04em;
    transition: border-color 160ms ease;
  }
  .src-tag:hover {
    border-color: var(--peacock, #1E4960);
  }

  /* Typing indicator — vermillion dots */
  .typing {
    display: flex;
    gap: 5px;
    padding: 4px 0;
  }
  .typing span {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--vermillion, #B84A2E);
    animation: bounce 1.4s infinite ease-in-out;
  }
  .typing span:nth-child(2) { animation-delay: 0.16s; }
  .typing span:nth-child(3) { animation-delay: 0.32s; }
  @keyframes bounce {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
    40% { transform: scale(1); opacity: 1; }
  }

  /* Composer — Atlas: 1.5px ink border, italic Source Serif placeholder, vermillion send pill */
  .composer {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 18px;
    margin-top: 12px;
    background: var(--paper, #F4EFE6);
    border: 1.5px solid var(--ink, #1B140E);
    border-radius: 8px;
  }
  .composer input {
    flex: 1;
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 15px;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--ink, #1B140E);
    outline: none;
  }
  .composer input::placeholder {
    color: var(--mist, #6E665E);
    font-style: italic;
  }

  .send-btn {
    background: var(--vermillion, #B84A2E);
    color: var(--paper, #F4EFE6);
    border: 0;
    border-radius: 99px;
    padding: 8px 16px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background 160ms ease, transform 160ms ease;
  }
  .send-btn:hover:not(:disabled) {
    background: var(--vermillion-d, #8E331E);
    transform: translateY(-1px);
  }
  .send-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .send-btn svg { width: 16px; height: 16px; }

  @media (max-width: 640px) {
    .chat { height: calc(100dvh - 160px); min-height: 320px; }
    .empty-title { font-size: 18px; }
    .empty-sub { font-size: 13px; }
    .pill { font-size: 12px; padding: 6px 11px; }
    .bubble.user-bubble { max-width: 88%; font-size: 14px; }
    .ai-text.prose { font-size: 15px; }
    .bubble.ai-bubble::after { left: 100px; }
    .composer { padding: 10px 14px; }
    .composer input { font-size: 14px; }
    .send-btn { padding: 6px 12px; }
  }
</style>
