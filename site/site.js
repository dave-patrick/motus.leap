// motus.leap landing page behaviour. Everything here is progressive:
// without JS the page shows the finished state of each illustration.

const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');

/* ---- Hero: example videos leap from Watch later into playlists ---- */
const stage = document.getElementById('stage');
if (stage) {
  const statusEl = document.getElementById('sorter-status');
  const replayBtn = document.getElementById('sorter-replay');
  const pristine = stage.innerHTML;
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  let run = 0;

  // Fly a copy of the thumbnail along an arc (the "leap") into the playlist cover.
  function leap(from, to) {
    const s = stage.getBoundingClientRect();
    const a = from.getBoundingClientRect(), b = to.getBoundingClientRect();
    const clone = from.cloneNode(true);
    clone.classList.add('leaper');
    Object.assign(clone.style, { left: `${a.left - s.left}px`, top: `${a.top - s.top}px`, width: `${a.width}px`, margin: 0 });
    stage.append(clone);
    const dx = b.left - a.left + (b.width - a.width) / 2, dy = b.top - a.top + (b.height - a.height) / 2;
    const scale = b.width / a.width, lift = Math.min(140, Math.abs(dx) * 0.45 + 50);
    const frames = [];
    for (let i = 0; i <= 16; i++) {
      const t = i / 16;
      const x = dx * t, y = dy * t - 4 * lift * t * (1 - t); // parabola: up, over, down
      frames.push({ transform: `translate(${x}px, ${y}px) scale(${1 + (scale - 1) * t}) rotate(${Math.sin(t * Math.PI) * -6}deg)` });
    }
    return clone.animate(frames, { duration: 640, easing: 'cubic-bezier(.45,.05,.35,1)', fill: 'forwards' })
      .finished.then(() => clone.remove());
  }

  function settle(row, quick) {
    const name = row.dataset.to;
    const pl = stage.querySelector(`.pl[data-list="${name}"]`);
    const countEls = pl.querySelectorAll('.pl-count, .pl-badge b');
    const n = Number(countEls[0].textContent) + 1;
    countEls.forEach((el) => { el.textContent = n; });
    pl.classList.remove('bump'); if (!quick) { void pl.offsetWidth; pl.classList.add('bump'); }
    row.classList.add('gone');
    const inbox = stage.querySelector('#inbox-count');
    inbox.textContent = Number(inbox.textContent) - 1;
  }

  function markMoved(row) {
    row.classList.remove('gone', 'active');
    row.querySelector('.chan').textContent = `Moved to ${row.dataset.to}`;
    row.querySelector('.verdict').textContent = '';
    row.classList.add('moved');
    stage.querySelector('.inbox-list').append(row);
  }

  async function play() {
    const id = ++run;
    stage.innerHTML = pristine;
    const rows = [...stage.querySelectorAll('.inbox-row[data-to]')];
    const waiting = [...stage.querySelectorAll('.inbox-row:not([data-to])')];
    if (reduceMotion.matches) {
      rows.forEach((r) => { settle(r, true); markMoved(r); });
    } else {
      await wait(600);
      for (const row of rows) {
        if (id !== run) return;
        const to = row.dataset.to;
        const verdict = row.querySelector('.verdict');
        row.classList.add('active');
        verdict.textContent = `Suggested: ${to}`;
        statusEl.textContent = `motus.leap suggests ${to} for "${row.querySelector('.title').textContent}".`;
        await wait(480);
        if (id !== run) return;
        verdict.textContent = '✓ Confirmed';
        verdict.classList.add('ok');
        await wait(260);
        if (id !== run) return;
        verdict.textContent = '';
        const target = stage.querySelector(`.pl[data-list="${to}"] .pl-cover`);
        const flight = leap(row.querySelector('.thumb'), target);
        row.classList.add('gone');
        await flight;
        if (id !== run) return;
        settle(row);
        markMoved(row);
        await wait(120);
      }
    }
    // collapse sorted rows, mark the rest as waiting for review
    waiting.forEach((r) => { r.classList.add('waiting'); r.querySelector('.verdict').textContent = 'Needs your review'; });
    statusEl.textContent = `${rows.length} example videos moved after confirmation. ${waiting.length} still wait for your review.`;
  }

  replayBtn?.addEventListener('click', play);
  (document.fonts?.ready ?? Promise.resolve()).then(play);
}

/* ---- Review board: move example videos with a view transition ---- */
const board = document.getElementById('board');
if (board) {
  const status = document.getElementById('board-status');
  const reset = document.getElementById('board-reset');
  const initial = board.innerHTML;
  const names = { travel: 'Travel & places', workshop: 'Workshop' };
  const $ = (sel) => board.querySelector(sel);

  // A stable name per video lets the browser morph it from one list to another.
  const nameVideos = () => board.querySelectorAll('.video').forEach((el, i) => {
    el.style.viewTransitionName = `video-${el.dataset.id || 'p' + i}`;
  });

  const withTransition = (update) => {
    if (!document.startViewTransition || reduceMotion.matches) { update(); return; }
    document.startViewTransition(update);
  };

  const refreshCounts = () => {
    $('#waiting-count').textContent = board.querySelectorAll('#review-list .video:not(.left-alone)').length;
    board.querySelectorAll('.playlist').forEach((pl) => {
      pl.querySelector('.pane-count').textContent = pl.querySelectorAll('.video').length;
    });
  };

  const confirmMove = (item) => {
    const to = item.dataset.to;
    const title = item.querySelector('.video-title').textContent;
    withTransition(() => {
      board.querySelectorAll('.just-placed').forEach((el) => el.classList.remove('just-placed'));
      const thumb = document.createElement('span');
      thumb.className = 'thumb';
      const name = document.createElement('p');
      name.className = 'video-title';
      name.textContent = title;
      item.replaceChildren(thumb, name);
      item.classList.add('placed', 'just-placed');
      $(`.playlist[data-list="${to}"] .playlist-items`).prepend(item);
      refreshCounts();
    });
    status.textContent = `Moved "${title}" to ${names[to]} in this example. Nothing on YouTube changed.`;
    reset.hidden = false;
  };

  const leave = (item) => {
    const title = item.querySelector('.video-title').textContent;
    withTransition(() => {
      item.classList.add('left-alone');
      item.querySelector('.video-actions').remove();
      $('#review-list').append(item);
      refreshCounts();
    });
    status.textContent = `Left "${title}" where it is. Nothing moves without your confirmation.`;
    reset.hidden = false;
  };

  board.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    const item = btn?.closest('.video');
    if (!item) return;
    if (btn.classList.contains('btn-confirm')) confirmMove(item);
    else if (btn.classList.contains('btn-skip')) leave(item);
  });

  reset.addEventListener('click', () => {
    withTransition(() => {
      board.innerHTML = initial;
      nameVideos();
    });
    status.textContent = 'Example board reset.';
    reset.hidden = true;
  });

  nameVideos();
}
