<script lang="ts">
  /**
   * FindingButton.svelte — vermillion "A finding" pill on the strip.
   * Click → fires `finer:show-finding` which FactCard listens for.
   */
  function handleClick() {
    window.dispatchEvent(new CustomEvent('finer:show-finding', {}));
  }
</script>

<button class="finding-btn" onclick={handleClick} aria-label="Show me a finding from the data">
  <svg viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <path d="M2 6a4 4 0 1 1 1.17 2.83" stroke="#F4EFE6" stroke-width="1.4" stroke-linecap="round"/>
    <path d="M2 9.5V7h2.5" stroke="#F4EFE6" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="6" cy="6" r="0.8" fill="#F4EFE6"/>
    <circle cx="8" cy="4.5" r="0.55" fill="#F4EFE6"/>
    <circle cx="4.5" cy="8" r="0.55" fill="#F4EFE6"/>
  </svg>
  A finding
</button>

<style>
  .finding-btn {
    align-self: center;
    margin-right: 16px;
    /* Don't let the strip's flex cells squish the pill on small screens */
    flex-shrink: 0;
    background: #B84A2E;
    color: #F4EFE6;
    font-family: 'Inter', sans-serif;
    font-size: 9.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 9px 14px;
    border: 0;
    border-radius: 99px;
    box-shadow: 0 2px 0 #8E331E, 0 6px 14px rgba(184, 74, 46, 0.18);
    display: inline-flex;
    align-items: center;
    gap: 7px;
    cursor: pointer;
    transition:
      transform 160ms cubic-bezier(0.32, 0.72, 0.40, 1.00),
      box-shadow 160ms cubic-bezier(0.32, 0.72, 0.40, 1.00);
  }
  .finding-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 0 #8E331E, 0 10px 22px rgba(184, 74, 46, 0.28);
  }
  .finding-btn:hover svg {
    animation: spin 800ms cubic-bezier(0.20, 0.80, 0.20, 1.00);
  }
  .finding-btn:active {
    transform: translateY(0);
    box-shadow: 0 2px 0 #8E331E, 0 6px 14px rgba(184, 74, 46, 0.18);
    transition-duration: 80ms;
  }
  .finding-btn svg { width: 12px; height: 12px; }

  @keyframes spin {
    from { transform: rotate(0); }
    to   { transform: rotate(360deg); }
  }

  @media (max-width: 760px) {
    /* On phones the strip hides the spacer + search, so the pill sits
       flush against the Where cell's right separator. Add left margin
       so it doesn't visually cross/touch that separator, shrink the
       pill, and tighten the shadow so it doesn't overshoot the 50px-
       tall strip's bottom border. */
    .finding-btn {
      margin-left: 10px;
      margin-right: 10px;
      padding: 7px 10px;
      font-size: 9px;
      letter-spacing: 0.10em;
      gap: 5px;
      box-shadow: 0 1px 0 #8E331E, 0 2px 4px rgba(184, 74, 46, 0.16);
    }
    .finding-btn:hover {
      box-shadow: 0 2px 0 #8E331E, 0 3px 6px rgba(184, 74, 46, 0.22);
    }
    .finding-btn svg { width: 11px; height: 11px; }
  }
  /* Very narrow phones (≤380px): collapse to icon only so the pill
     never overlaps the Where cell separator. The aria-label keeps it
     accessible. */
  @media (max-width: 380px) {
    .finding-btn {
      font-size: 0;        /* hide text node */
      padding: 8px;
      gap: 0;
    }
    .finding-btn svg { width: 14px; height: 14px; }
  }
</style>
