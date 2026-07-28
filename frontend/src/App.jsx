import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch } from './api';
import { 
  LayoutDashboard, 
  ListVideo, 
  Users, 
  Wrench, 
  Bot, 
  Settings as SettingsIcon, 
  RefreshCw, 
  ExternalLink, 
  CheckCircle2, 
  XCircle,
  Play,
  Trash2,
  Copy,
  Search,
  Sparkles,
  ArrowRight,
  ShieldCheck
} from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedPlaylistId, setSelectedPlaylistId] = useState(null);

  return (
    <div className="min-h-screen flex flex-col bg-[#121419] text-[#e5e5e5]">
      {/* Top Header Navigation */}
      <header className="px-6 py-3 bg-[#16191f] border-b border-[#2a2f3a] flex items-center justify-between gap-4 sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#2f8fc9] to-[#5ba5d6] flex items-center justify-center text-white font-bold text-lg shadow-lg">
            M
          </div>
          <div>
            <h1 className="text-base font-bold text-white leading-none">motus.leap</h1>
            <p className="text-[10px] text-gray-400 mt-0.5">YouTube Playlist Agent v2.0</p>
          </div>
        </div>

        {/* Primary Navigation Tabs */}
        <nav className="flex items-center gap-1 bg-[#0f1115] p-1 rounded-xl border border-[#2a2f3a]">
          <NavBtn active={activeTab === 'dashboard'} onClick={() => { setActiveTab('dashboard'); setSelectedPlaylistId(null); }}>
            <LayoutDashboard className="w-4 h-4" /> Dashboard
          </NavBtn>
          <NavBtn active={activeTab === 'playlists'} onClick={() => { setActiveTab('playlists'); setSelectedPlaylistId(null); }}>
            <ListVideo className="w-4 h-4" /> Playlists
          </NavBtn>
          <NavBtn active={activeTab === 'subscriptions'} onClick={() => { setActiveTab('subscriptions'); setSelectedPlaylistId(null); }}>
            <Users className="w-4 h-4" /> Subscriptions
          </NavBtn>
          <NavBtn active={activeTab === 'maintenance'} onClick={() => { setActiveTab('maintenance'); setSelectedPlaylistId(null); }}>
            <Wrench className="w-4 h-4" /> Maintenance
          </NavBtn>
          <NavBtn active={activeTab === 'ai-hub'} onClick={() => { setActiveTab('ai-hub'); setSelectedPlaylistId(null); }}>
            <Bot className="w-4 h-4 text-[#2f8fc9]" /> AI Hub
          </NavBtn>
          <NavBtn active={activeTab === 'settings'} onClick={() => { setActiveTab('settings'); setSelectedPlaylistId(null); }}>
            <SettingsIcon className="w-4 h-4" /> Settings
          </NavBtn>
        </nav>
      </header>

      {/* Main View Area */}
      <main className="flex-1 p-6 max-w-[1600px] w-full mx-auto">
        {activeTab === 'dashboard' && <DashboardView onOpenPlaylist={(id) => { setSelectedPlaylistId(id); setActiveTab('playlist-detail'); }} />}
        {activeTab === 'playlists' && !selectedPlaylistId && <PlaylistsView onSelectPlaylist={(id) => { setSelectedPlaylistId(id); setActiveTab('playlist-detail'); }} />}
        {activeTab === 'playlist-detail' && selectedPlaylistId && <PlaylistDetailView playlistId={selectedPlaylistId} onBack={() => setActiveTab('playlists')} />}
        {activeTab === 'subscriptions' && <SubscriptionsView />}
        {activeTab === 'maintenance' && <MaintenanceView />}
        {activeTab === 'ai-hub' && <AIChatHubView />}
        {activeTab === 'settings' && <SettingsView />}
      </main>
    </div>
  );
}

function NavBtn({ children, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all duration-200 cursor-pointer ${
        active 
          ? 'bg-[#2f8fc9] text-white shadow-md' 
          : 'text-gray-400 hover:text-white hover:bg-white/5'
      }`}
    >
      {children}
    </button>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Dashboard View
   ───────────────────────────────────────────────────────────────────────────── */
function DashboardView({ onOpenPlaylist }) {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: async () => {
      const res = await apiFetch('/api/stats');
      return res.json();
    },
  });

  const { data: playlists } = useQuery({
    queryKey: ['playlists'],
    queryFn: async () => {
      const res = await apiFetch('/api/playlists');
      const data = await res.json();
      return Array.isArray(data) ? data : (data.playlists || []);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Dashboard Overview</h2>
          <p className="text-xs text-gray-400">Library statistics and quick control panel.</p>
        </div>
      </div>

      {/* Stats Bento Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bento-card p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-[#2f8fc9]/10 border border-[#2f8fc9]/30 flex items-center justify-center text-[#2f8fc9]">
            <ListVideo className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400">Total Playlists</p>
            <h3 className="text-2xl font-bold text-white">{isLoading ? '...' : stats?.total_playlists ?? 0}</h3>
          </div>
        </div>

        <div className="bento-card p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400">
            <Play className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400">Total Videos</p>
            <h3 className="text-2xl font-bold text-white">{isLoading ? '...' : stats?.total_videos ?? 0}</h3>
          </div>
        </div>

        <div className="bento-card p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs font-medium text-gray-400">Subscriptions</p>
            <h3 className="text-2xl font-bold text-white">{isLoading ? '...' : stats?.total_subscriptions ?? 0}</h3>
          </div>
        </div>
      </div>

      {/* Recent Playlists Grid */}
      <div className="bento-card p-5 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center gap-2">
          <ListVideo className="w-4 h-4 text-[#2f8fc9]" /> Playlists ({playlists?.length || 0})
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {playlists?.slice(0, 6).map((p) => (
            <div
              key={p.id}
              onClick={() => onOpenPlaylist(p.id)}
              className="p-3 bg-[#16191f] border border-[#2a2f3a] rounded-xl hover:border-[#2f8fc9]/50 transition-all cursor-pointer flex items-center gap-3"
            >
              <div className="w-16 h-12 rounded-lg bg-[#0f1115] overflow-hidden flex-shrink-0">
                <img src={p.thumbnail || `https://i.ytimg.com/vi/${p.id}/hqdefault.jpg`} alt="" className="w-full h-full object-cover" />
              </div>
              <div className="min-w-0 flex-1">
                <h4 className="text-xs font-semibold text-white truncate">{p.title || p.name}</h4>
                <p className="text-[10px] text-gray-400">{p.video_count || 0} videos</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Playlists View
   ───────────────────────────────────────────────────────────────────────────── */
function PlaylistsView({ onSelectPlaylist }) {
  const { data: playlists, isLoading } = useQuery({
    queryKey: ['playlists'],
    queryFn: async () => {
      const res = await apiFetch('/api/playlists');
      const data = await res.json();
      return Array.isArray(data) ? data : (data.playlists || []);
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Playlists</h2>
          <p className="text-xs text-gray-400">Browse and manage your YouTube playlists.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {playlists?.map((p) => (
          <div
            key={p.id}
            onClick={() => onSelectPlaylist(p.id)}
            className="bento-card p-4 hover:border-[#2f8fc9]/50 transition-all cursor-pointer flex flex-col gap-3 group"
          >
            <div className="aspect-video rounded-lg bg-[#0f1115] overflow-hidden relative">
              <img src={p.thumbnail || `https://i.ytimg.com/vi/${p.id}/hqdefault.jpg`} alt="" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
              <span className="absolute bottom-2 right-2 bg-black/80 text-white text-[10px] font-mono px-2 py-0.5 rounded font-bold">
                {p.video_count || 0} vids
              </span>
            </div>
            <div>
              <h3 className="text-sm font-bold text-white truncate group-hover:text-[#2f8fc9] transition-colors">{p.title || p.name}</h3>
              <p className="text-xs text-gray-400 capitalize">{p.privacy || 'private'}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Playlist Detail View (Batch Infinite Scroll)
   ───────────────────────────────────────────────────────────────────────────── */
function PlaylistDetailView({ playlistId, onBack }) {
  const [search, setSearch] = useState('');

  const { data: videos, isLoading } = useQuery({
    queryKey: ['playlist-videos', playlistId],
    queryFn: async () => {
      const res = await apiFetch(`/api/youtube/videos?playlist_id=${playlistId}`);
      const data = await res.json();
      return data.videos || [];
    },
  });

  const filteredVideos = videos?.filter((v) =>
    search ? (v.title || '').toLowerCase().includes(search.toLowerCase()) : true
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onBack} className="px-3.5 py-1.5 rounded-lg bg-[#20242c] hover:bg-[#2f8fc9] text-white text-xs font-semibold flex items-center gap-2 transition-all">
          <ArrowRight className="w-4 h-4 rotate-180" /> Back to Playlists
        </button>
      </div>

      <div className="bento-card p-4 flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search videos in playlist..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[#20242c] border border-[#2a2f3a] text-gray-200 text-xs rounded-lg pl-9 pr-3 py-2 outline-none focus:border-[#2f8fc9]"
          />
        </div>
        <span className="text-xs text-gray-400 font-medium">{filteredVideos?.length || 0} videos</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filteredVideos?.map((v) => (
          <div key={v.video_id || v.id} className="bg-[#16191f] border border-[#2a2f3a] rounded-xl overflow-hidden p-3 space-y-2">
            <div className="aspect-video rounded-lg bg-[#0a0c10] overflow-hidden relative">
              <img src={v.thumbnail || `https://i.ytimg.com/vi/${v.video_id}/hqdefault.jpg`} alt="" className="w-full h-full object-cover" />
              <span className="absolute bottom-1.5 right-1.5 bg-black/80 text-white text-[9px] font-mono px-1.5 py-0.5 rounded font-bold">
                {v.duration_formatted || '0:00'}
              </span>
            </div>
            <h4 className="text-xs font-semibold text-white line-clamp-2">{v.title}</h4>
            <p className="text-[10px] text-gray-400">{v.channel_title}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Subscriptions View
   ───────────────────────────────────────────────────────────────────────────── */
function SubscriptionsView() {
  const { data: subs, isLoading } = useQuery({
    queryKey: ['subscriptions'],
    queryFn: async () => {
      const res = await apiFetch('/api/subscriptions');
      const data = await res.json();
      return data.channels || [];
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Subscriptions ({subs?.length || 0})</h2>
        <p className="text-xs text-gray-400">Channels you are subscribed to on YouTube.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {subs?.map((s) => (
          <div key={s.id} className="bento-card p-4 flex items-center gap-3">
            <img src={s.thumbnail} alt="" className="w-12 h-12 rounded-full object-cover bg-[#0f1115]" />
            <div className="min-w-0 flex-1">
              <h4 className="text-xs font-bold text-white truncate">{s.title}</h4>
              <p className="text-[10px] text-gray-400">{s.subscribers || 0} subscribers</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Maintenance View
   ───────────────────────────────────────────────────────────────────────────── */
function MaintenanceView() {
  const queryClient = useQueryClient();

  const removeDeletedMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch('/api/maintenance/remove-deleted', { method: 'POST' });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  const movePrivateMutation = useMutation({
    mutationFn: async () => {
      const res = await apiFetch('/api/maintenance/move-private', { method: 'POST' });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Maintenance Actions</h2>
        <p className="text-xs text-gray-400">Clean up deleted videos and move private items.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bento-card p-6 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Trash2 className="w-4 h-4 text-red-400" /> Remove Deleted Videos
          </h3>
          <p className="text-xs text-gray-400">Scans your playlists and removes deleted/unavailable videos.</p>
          <button
            onClick={() => removeDeletedMutation.mutate()}
            disabled={removeDeletedMutation.isPending}
            className="px-4 py-2.5 bg-red-600 hover:bg-red-700 text-white font-bold rounded-lg text-xs transition-colors cursor-pointer"
          >
            {removeDeletedMutation.isPending ? 'Cleaning...' : 'Remove Deleted Videos'}
          </button>
        </div>

        <div className="bento-card p-6 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-amber-400" /> Move Private Videos
          </h3>
          <p className="text-xs text-gray-400">Moves private videos from your playlists into a "Check Later" playlist.</p>
          <button
            onClick={() => movePrivateMutation.mutate()}
            disabled={movePrivateMutation.isPending}
            className="px-4 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-lg text-xs transition-colors cursor-pointer"
          >
            {movePrivateMutation.isPending ? 'Moving...' : 'Move Private Videos'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   AI Chat Hub View
   ───────────────────────────────────────────────────────────────────────────── */
function AIChatHubView() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hello! I am your YouTube Agent assistant. How can I help organize your playlists today?' }
  ]);
  const [input, setInput] = useState('');

  const handleSend = () => {
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { role: 'user', text: input }]);
    const currentInput = input;
    setInput('');
    setTimeout(() => {
      setMessages((prev) => [...prev, { role: 'assistant', text: `I received your request: "${currentInput}". Analyzing your playlists...` }]);
    }, 600);
  };

  return (
    <div className="bento-card p-6 space-y-4 max-w-4xl mx-auto min-h-[600px] flex flex-col">
      <div className="flex items-center gap-2 pb-3 border-b border-[#2a2f3a]">
        <Bot className="w-5 h-5 text-[#2f8fc9]" />
        <h3 className="text-sm font-bold text-white">AI Assistant Hub</h3>
      </div>

      <div className="flex-1 overflow-y-auto space-y-3 p-2">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-lg p-3 rounded-xl text-xs ${m.role === 'user' ? 'bg-[#2f8fc9] text-white' : 'bg-[#20242c] text-gray-200 border border-[#2a2f3a]'}`}>
              {m.text}
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 pt-3 border-t border-[#2a2f3a]">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask AI assistant to organize playlists or find duplicates..."
          className="flex-1 bg-[#20242c] border border-[#2a2f3a] text-gray-200 text-xs rounded-xl px-4 py-2.5 outline-none focus:border-[#2f8fc9]"
        />
        <button onClick={handleSend} className="px-4 py-2.5 bg-[#2f8fc9] hover:bg-[#2a7db8] text-white font-bold rounded-xl text-xs transition-colors cursor-pointer">
          Send
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Settings View
   ───────────────────────────────────────────────────────────────────────────── */
function SettingsView() {
  return (
    <div className="bento-card p-6 space-y-6 max-w-4xl mx-auto">
      <h2 className="text-xl font-bold text-white flex items-center gap-2">
        <SettingsIcon className="w-5 h-5 text-[#2f8fc9]" /> Application Settings
      </h2>

      <div className="space-y-4">
        <div className="p-4 bg-[#16191f] border border-[#2a2f3a] rounded-xl flex items-center justify-between">
          <div>
            <h4 className="text-xs font-bold text-white">YouTube Connection Status</h4>
            <p className="text-[10px] text-gray-400">OAuth token authentication state.</p>
          </div>
          <span className="px-3 py-1 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold rounded-lg flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4" /> Connected
          </span>
        </div>
      </div>
    </div>
  );
}
