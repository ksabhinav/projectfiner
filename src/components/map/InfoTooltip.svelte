<script lang="ts">
  import { onMount } from 'svelte';
  import { onFiner } from '../../lib/map-bridge';

  interface Props {}
  let {}: Props = $props();

  let visible = $state(false);
  let text = $state('');
  let posLeft = $state(0);
  let posTop = $state(0);

  function show(detail: { text: string; rect: DOMRect }) {
    if (!detail.text) {
      visible = false;
      return;
    }
    text = detail.text;
    posLeft = detail.rect.right + 8;
    posTop = detail.rect.top - 8;
    visible = true;
  }

  function hide() {
    visible = false;
  }

  function handleClickOutside(e: MouseEvent | TouchEvent) {
    const target = e.target as HTMLElement;
    if (!target.closest('.info-btn')) {
      hide();
    }
  }

  onMount(() => {
    const unsubs = [
      onFiner('showInfo', show),
      onFiner('hideInfo', hide),
    ];

    document.addEventListener('touchstart', handleClickOutside);

    return () => {
      unsubs.forEach(fn => fn());
      document.removeEventListener('touchstart', handleClickOutside);
    };
  });
</script>

<div
  class="info-popover"
  class:visible
  style="left:{posLeft}px;top:{posTop}px"
>
  {text}
</div>

<style>
  .info-popover {
    display: none;
    position: fixed;
    z-index: 2000;
    background: rgba(255,255,255,0.97);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(224,221,216,0.6);
    border-radius: 8px;
    padding: 10px 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    font-family: 'Inter', sans-serif;
    font-size: 10px;
    font-weight: 400;
    color: #555048;
    line-height: 1.6;
    width: 220px;
    pointer-events: none;
    animation: infoAppear 0.15s ease;
  }

  .info-popover.visible {
    display: block;
  }

  @keyframes infoAppear {
    0% { opacity: 0; transform: translateY(-4px); }
    100% { opacity: 1; transform: translateY(0); }
  }
</style>
