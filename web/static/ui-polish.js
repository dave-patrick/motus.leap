/* Shared dialog behavior and friendly alternatives to expert ID/cron inputs. */
(() => {
  'use strict';
  if (window.__uiPolish) return;
  window.__uiPolish = true;
  const visible = el => !el.hidden && !el.classList.contains('hidden') && el.getClientRects().length > 0;
  const focusables = el => [...el.querySelectorAll('button,a[href],input,select,textarea,[tabindex="0"]')]
    .filter(node => !node.disabled && node.getClientRects().length);
  const dialogs = new Map();
  let dialogNumber = 0;
  let active = null;
  function syncDialogs() {
    for (const el of document.querySelectorAll('[id$="-modal"],.fixed.inset-0.items-center')) {
      if (!el.querySelector('h2,h3,[id$="-title"]')) continue;
      if (!dialogs.has(el)) {
        const heading = el.querySelector('h2,h3,[id$="-title"]');
        heading.id ||= 'dialog-title-' + dialogNumber++;
        el.setAttribute('role', 'dialog'); el.setAttribute('aria-modal', 'true');
        el.setAttribute('aria-labelledby', heading.id); el.tabIndex = -1;
        for (const button of el.querySelectorAll('button')) {
          if (!button.textContent.trim() && !button.hasAttribute('aria-label')) button.setAttribute('aria-label', button.title || 'Close dialog');
        }
        dialogs.set(el, {open:false,previous:null});
      }
      const state = dialogs.get(el), open = visible(el);
      if (open && !state.open) {
        for (const select of el.querySelectorAll('select[data-input-id]')) select.value = document.getElementById(select.dataset.inputId)?.value || '';
        state.previous = document.activeElement; state.open = true; active = el;
        (focusables(el)[0] || el).focus();
      } else if (!open && state.open) {
        state.open = false;
        if (state.previous?.isConnected) state.previous.focus();
        if (active === el) active = null;
      }
    }
    for (const [el,state] of dialogs) if (!el.isConnected) {
      if (state.open && state.previous?.isConnected) state.previous.focus();
      if (active === el) active = null;
      dialogs.delete(el);
    }
  }
  document.addEventListener('keydown', event => {
    if (!active || !visible(active)) return;
    const nodes = focusables(active);
    if (event.key === 'Tab') {
      if (!nodes.length) { event.preventDefault(); active.focus(); return; }
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (event.shiftKey && (document.activeElement === first || !active.contains(document.activeElement))) {event.preventDefault();last.focus();}
      else if (!event.shiftKey && (document.activeElement === last || !active.contains(document.activeElement))) {event.preventDefault();first.focus();}
    }
    if (event.key === 'Escape') {
      const close = active.querySelector('[id$="-close"],button[aria-label="Close dialog"],button[title="Close"]') || [...active.querySelectorAll('button')].find(button => /^(close|cancel)$/i.test(button.textContent.trim()));
      if (close) {event.preventDefault();close.click();}
    }
  }, true);
  new MutationObserver(syncDialogs).observe(document.body, {subtree:true,childList:true,attributes:true,attributeFilter:['class','hidden']});
  syncDialogs();

  async function getJSON(url) {
    const response = await (window.authFetch || window.fetch)(url);
    if (!response.ok) throw new Error('Could not load your library. Try again.');
    return response.json();
  }
  const option = (value,text) => {const el=document.createElement('option');el.value=value;el.textContent=text;return el;};
  let playlistPromise;
  function playlists() {
    playlistPromise ||= getJSON('/api/playlists').then(data => data.playlists || []).catch(error => {playlistPromise=null;throw error;});
    return playlistPromise;
  }
  async function addLibraryChoice(id, kind) {
    const input = document.getElementById(id); if (!input) return;
    const select = document.createElement('select'); select.className = 'ui-control w-full mb-2';
    select.dataset.inputId = id;
    select.setAttribute('aria-label', kind === 'channel' ? 'Choose a subscribed channel' : 'Choose a playlist');
    select.append(option('',kind === 'channel' ? 'Choose a subscribed channel…' : 'Choose a playlist…'));
    input.before(select);
    select.addEventListener('change', () => {input.value=select.value;input.dispatchEvent(new Event('input',{bubbles:true}));});
    const details = document.createElement('details'); details.className='expert-input';
    const summary=document.createElement('summary');summary.textContent='Enter an ID manually';details.append(summary);
    input.before(details);details.append(input);
    input.addEventListener('change',()=>{select.value=input.value;});
    try {
      const rows=kind==='channel'?(await getJSON('/api/subscriptions')).channels || []:await playlists();
      for (const row of rows) select.append(option(row.id || row.channel_id || '',row.title || row.channel_title || row.id));
      select.value=input.value;
    } catch (error) {details.open=true; select.options[0].textContent=error.message;}
  }
  ['rule-playlist','job-playlist'].forEach(id=>addLibraryChoice(id,'playlist'));
  addLibraryChoice('new-channel-id','channel');

  const cron=document.getElementById('job-cron');
  if (cron) {
    const choices=document.createElement('select'); choices.className='ui-control w-full mb-2'; choices.setAttribute('aria-label','Schedule frequency');
    [['','Choose a schedule…'],['0 * * * *','Every hour'],['0 3 * * *','Every day at 03:00'],['0 3 * * 1','Every Monday at 03:00'],['custom','Custom cron schedule']].forEach(([value,text])=>choices.append(option(value,text)));
    cron.before(choices);
    cron.hidden=!cron.value;
    choices.addEventListener('change',()=>{if(choices.value!=='custom'){cron.value=choices.value;cron.dispatchEvent(new Event('input',{bubbles:true}));}cron.hidden=choices.value!=='custom';});
    cron.addEventListener('input',()=>{const match=[...choices.options].find(opt=>opt.value===cron.value);choices.value=match?match.value:'custom';cron.hidden=!(!match);});
    const hint=document.createElement('p');hint.className='text-sm text-gray-400';hint.textContent='Times use the server schedule timezone. Custom schedules accept five cron fields.';cron.after(hint);
  }

  // Existing textarea remains the submitted selection, retaining expert paste and safeguards.
  const tagTarget=document.getElementById('tag-videos');
  if(tagTarget) {
    const source=document.createElement('select');source.id='tag-source';source.className='ui-control w-full mb-2';source.setAttribute('aria-label','Playlist to browse for tagging');source.append(option('','Choose a playlist to browse…'));tagTarget.before(source);
    playlists().then(rows=>rows.forEach(row=>source.append(option(row.id,row.title || row.id)))).catch(()=>{});
  }
  for (const [sourceId,targetId] of [['move-source','move-videos'],['delete-playlist','delete-videos'],['tag-source','tag-videos']]) {
    const source=document.getElementById(sourceId), target=document.getElementById(targetId);if(!source||!target)continue;
    const box=document.createElement('div');box.className='video-picker space-y-2';
    const search=document.createElement('input');search.type='search';search.className='ui-control w-full';search.placeholder='Search videos in the selected playlist';search.setAttribute('aria-label','Search playlist videos');
    const list=document.createElement('div');list.className='video-picker-list';list.setAttribute('aria-live','polite');
    box.append(search,list);target.before(box);
    const details=document.createElement('details');details.className='expert-input';const summary=document.createElement('summary');summary.textContent='Paste or inspect selected video IDs';details.append(summary);target.before(details);details.append(target);
    let request=0,timer;
    async function load() {
      const current=++request;list.replaceChildren();if(!source.value){list.textContent='Choose a source playlist to browse its videos.';return;}
      list.textContent='Loading videos…';
      try {
        const params=new URLSearchParams({playlist_id:source.value,page:'1',page_size:'50',search:search.value});
        const data=await getJSON('/api/youtube/videos?'+params);if(current!==request)return;
        list.replaceChildren();const selected=new Set(target.value.split(/[,\n]/).map(value=>value.trim()));
        for(const video of data.videos || []) {
          const id=video.video_id || video.id; if(!id)continue;
          const label=document.createElement('label');label.className='video-choice';
          const check=document.createElement('input');check.type='checkbox';check.value=id;check.checked=selected.has(id);check.setAttribute('aria-label','Select '+(video.title || id));
          const text=document.createElement('span');text.textContent=video.title || id;
          check.addEventListener('change',()=>{const ids=new Set(target.value.split(/[,\n]/).map(value=>value.trim()).filter(Boolean));check.checked?ids.add(id):ids.delete(id);target.value=[...ids].join('\n');});
          label.append(check,text);list.append(label);
        }
        if(!list.children.length)list.textContent='No matching videos.';
        if(data.pagination?.has_more){const note=document.createElement('p');note.textContent='Showing the first 50 matches. Refine your search for more videos.';list.append(note);}
      }catch(error){if(current===request)list.textContent=error.message;}
    }
    source.addEventListener('change',()=>{target.value='';search.value='';load();});
    target.addEventListener('input',()=>{const ids=new Set(target.value.split(/[,\n]/).map(value=>value.trim()).filter(Boolean));for(const check of list.querySelectorAll('input[type="checkbox"]'))check.checked=ids.has(check.value);});
    search.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(load,250);});load();
  }
})();
