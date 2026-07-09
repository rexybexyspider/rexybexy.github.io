/* ==========================================
   🎵 ربات موسیقی - منطق اصلی
   iTunes Search API + Signaling Server + Real-time Sync
   ========================================== */

// ==========================================
// تنظیمات
// ==========================================
const CONFIG = {
    // آیدی کاربر (از تلگرام یا localStorage)
    get USER_ID() {
        // ابتدا از URL param (برای تست)
        const urlParams = new URLSearchParams(window.location.search);
        const urlId = urlParams.get('user_id');
        if (urlId) {
            localStorage.setItem('user_id', urlId);
            return parseInt(urlId);
        }
        // از localStorage
        const stored = localStorage.getItem('user_id');
        if (stored) return parseInt(stored);
        // از تلگرام
        if (window.Telegram?.WebApp?.initDataUnsafe?.user?.id) {
            const id = Telegram.WebApp.initDataUnsafe.user.id;
            localStorage.setItem('user_id', id);
            return id;
        }
        // fallback: تولید یه آیدی موقت
        const tempId = -Math.floor(Math.random() * 1000000);
        localStorage.setItem('user_id', tempId);
        return tempId;
    },
    // URL سرور signaling - این رو باید با URL ngrok خودت عوض کنی
    SIGNALING_URL: 'https://your-ngrok-url.ngrok.io',
    ITUNES_API: 'https://itunes.apple.com/search',
};

// ==========================================
// State
// ==========================================
const State = {
    user: null,
    friends: [],
    requests: [],
    invites: [],
    history: [],
    searchResults: [],
    currentTrack: null,
    isPlaying: false,
    currentTime: 0,
    duration: 30, // preview ۳۰ ثانیه
    activeSession: null,
    eventSource: null,
    audio: null,
    lastSyncTime: 0,
    syncInterval: null,
    chatPollInterval: null,
    selectedEmoji: '🎵',
    currentTab: 'discover',
};

// ==========================================
// ابزارها
// ==========================================
function $(id) { return document.getElementById(id); }
function $$(sel) { return document.querySelectorAll(sel); }

function faNum(n) { return Number(n).toLocaleString('fa-IR'); }

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

function showToast(message, type = '') {
    const toast = $('toast');
    toast.textContent = message;
    toast.className = 'toast ' + type;
    setTimeout(() => toast.classList.add('hidden'), 2500);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ==========================================
// API client - ارتباط با سرور signaling
// ==========================================
const API = {
    async request(endpoint, method = 'GET', data = null) {
        const url = CONFIG.SIGNALING_URL + endpoint;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'X-User-Id': CONFIG.USER_ID.toString(),
            },
        };
        if (data) options.body = JSON.stringify(data);

        try {
            const response = await fetch(url, options);
            const result = await response.json();
            if (!response.ok || !result.ok) {
                throw new Error(result.error || 'خطای سرور');
            }
            return result.data;
        } catch (err) {
            console.error('API Error:', err);
            throw err;
        }
    },

    // کاربر
    async getMe() { return this.request('/api/me'); },
    async updateMe(data) { return this.request('/api/me', 'POST', data); },

    // دوستان
    async getFriends() { return this.request('/api/friends'); },
    async addFriend(friendId) { return this.request('/api/friends/add', 'POST', { friend_id: friendId }); },
    async acceptFriend(friendId) { return this.request('/api/friends/accept', 'POST', { friend_id: friendId }); },
    async getRequests() { return this.request('/api/friends/requests'); },

    // دعوت گوش دادن
    async sendListenInvite(friendId, track) {
        return this.request('/api/listen/invite', 'POST', { friend_id: friendId, track });
    },
    async acceptListenInvite(inviteId) {
        return this.request('/api/listen/accept', 'POST', { invite_id: inviteId });
    },
    async rejectListenInvite(inviteId) {
        return this.request('/api/listen/reject', 'POST', { invite_id: inviteId });
    },
    async getListenInvites() { return this.request('/api/listen/invites'); },

    // session
    async getSession(sessionId) { return this.request(`/api/session/${sessionId}`); },
    async updateSession(sessionId, data) { return this.request(`/api/session/${sessionId}/update`, 'POST', data); },
    async endSession(sessionId) { return this.request(`/api/session/${sessionId}/end`, 'POST'); },
    async getMessages(sessionId, since = 0) {
        return this.request(`/api/session/${sessionId}/messages?since=${since}`);
    },
    async sendMessage(sessionId, message) {
        return this.request(`/api/session/${sessionId}/messages`, 'POST', { message });
    },

    // history
    async getHistory() { return this.request('/api/history'); },
    async addHistory(track) { return this.request('/api/history', 'POST', { track }); },
};

// ==========================================
// iTunes Search API
// ==========================================
async function searchMusic(query) {
    if (!query.trim()) return [];
    const url = `${CONFIG.ITUNES_API}?term=${encodeURIComponent(query)}&media=music&limit=25`;
    try {
        const response = await fetch(url);
        const data = await response.json();
        return data.results || [];
    } catch (err) {
        console.error('iTunes search error:', err);
        showToast('خطا در سرچ موسیقی', 'error');
        return [];
    }
}

// ==========================================
// پلیر صوتی
// ==========================================
function initAudio() {
    State.audio = new Audio();
    State.audio.preload = 'auto';

    State.audio.addEventListener('timeupdate', () => {
        State.currentTime = State.audio.currentTime;
        updatePlayerProgress();
        updateNowPlayingProgress();
        updateSessionProgress();
    });

    State.audio.addEventListener('ended', () => {
        State.isPlaying = false;
        updatePlayButtons();
    });

    State.audio.addEventListener('play', () => {
        State.isPlaying = true;
        updatePlayButtons();
    });

    State.audio.addEventListener('pause', () => {
        State.isPlaying = false;
        updatePlayButtons();
    });

    State.audio.addEventListener('error', (e) => {
        console.error('Audio error:', e);
        showToast('خطا در پخش موسیقی', 'error');
    });
}

function playTrack(track) {
    if (!track.previewUrl) {
        showToast('این موسیقی preview نداره', 'error');
        return;
    }

    State.currentTrack = track;
    State.audio.src = track.previewUrl;
    State.audio.play().catch(err => {
        console.error('Play error:', err);
        showToast('نتونستم پخش کنم', 'error');
    });

    // آپدیت UI
    showPlayerBar(track);
    addTrackToHistory(track);
    updateTrackListHighlight(track);
}

function togglePlay() {
    if (!State.currentTrack) return;
    if (State.audio.paused) {
        State.audio.play();
    } else {
        State.audio.pause();
    }
}

function updatePlayButtons() {
    const playBtn = $('play-btn');
    const npPlay = $('np-play');
    const icon = State.isPlaying ? '⏸' : '▶';
    if (playBtn) playBtn.textContent = icon;
    if (npPlay) npPlay.textContent = icon;

    // آیکون equalizer در لیست
    const playingItem = document.querySelector('.track-item.playing');
    if (playingItem) {
        const indicator = playingItem.querySelector('.track-playing-indicator');
        if (indicator) indicator.style.opacity = State.isPlaying ? '1' : '0.3';
    }

    // آیکون artwork در now playing
    const npArtwork = $('np-artwork');
    const npVinyl = $('np-vinyl');
    if (npArtwork) {
        if (State.isPlaying) npArtwork.classList.add('playing');
        else npArtwork.classList.remove('playing');
    }
    if (npVinyl) {
        if (State.isPlaying) npVinyl.classList.add('spinning');
        else npVinyl.classList.remove('spinning');
    }
}

function showPlayerBar(track) {
    const bar = $('player-bar');
    bar.classList.remove('hidden');
    $('player-artwork').src = track.artworkUrl100 || '';
    $('player-title').textContent = track.trackName || 'نامشخص';
    $('player-artist').textContent = track.artistName || '';
}

function updatePlayerProgress() {
    if (!State.currentTrack) return;
    const pct = (State.currentTime / State.duration) * 100;
    $('progress-fill').style.width = pct + '%';
    $('current-time').textContent = formatTime(State.currentTime);
    $('total-time').textContent = formatTime(State.duration);
}

function updateNowPlayingProgress() {
    if (!State.currentTrack) return;
    const pct = (State.currentTime / State.duration) * 100;
    $('np-progress-fill').style.width = pct + '%';
    $('np-current').textContent = formatTime(State.currentTime);
    $('np-total').textContent = formatTime(State.duration);
}

function updateSessionProgress() {
    if (!State.activeSession) return;
    const pct = (State.currentTime / State.duration) * 100;
    $('session-progress-fill').style.width = pct + '%';
    $('session-current').textContent = formatTime(State.currentTime);
    $('session-total').textContent = formatTime(State.duration);
}

async function addTrackToHistory(track) {
    try {
        await API.addHistory(track);
    } catch (err) {
        // silent
    }
}

function updateTrackListHighlight(track) {
    $$('.track-item').forEach(item => {
        item.classList.remove('playing');
        if (item.dataset.trackId == track.trackId) {
            item.classList.add('playing');
        }
    });
}

// ==========================================
// رندر لیست آهنگ‌ها
// ==========================================
function renderTrackList(tracks, container) {
    if (!tracks || tracks.length === 0) {
        container.innerHTML = `
            <div class="discover-default">
                <div class="empty-art">🔇</div>
                <h3>چیزی پیدا نشد</h3>
                <p>یه چیز دیگه سرچ کن</p>
            </div>
        `;
        return;
    }

    container.innerHTML = tracks.map(t => {
        const isPlaying = State.currentTrack && State.currentTrack.trackId === t.trackId;
        const playingHtml = isPlaying && State.isPlaying
            ? `<div class="track-playing-indicator"><span></span><span></span><span></span></div>`
            : '';
        return `
            <div class="track-item ${isPlaying ? 'playing' : ''}" data-track-id="${t.trackId}">
                <img class="track-artwork" src="${t.artworkUrl100 || ''}" alt="" loading="lazy">
                <div class="track-info">
                    <div class="track-name">${escapeHtml(t.trackName || 'نامشخص')}</div>
                    <div class="track-artist">${escapeHtml(t.artistName || '')}</div>
                </div>
                <div class="track-actions">
                    ${playingHtml}
                    <button class="track-action-btn play-track">▶</button>
                </div>
            </div>
        `;
    }).join('');

    $$('.track-item').forEach(item => {
        item.onclick = () => {
            const trackId = parseInt(item.dataset.trackId);
            const track = tracks.find(t => t.trackId === trackId);
            if (track) playTrack(track);
        };
    });
}

// ==========================================
// سرچ
// ==========================================
let searchTimeout;
async function handleSearch(query) {
    clearTimeout(searchTimeout);
    if (!query.trim()) {
        $('search-results').innerHTML = '';
        $('discover-default').style.display = 'block';
        return;
    }

    $('discover-default').style.display = 'none';
    $('search-results').innerHTML = '<div style="text-align:center;padding:30px;color:#888;">🔍 در حال سرچ...</div>';

    searchTimeout = setTimeout(async () => {
        const results = await searchMusic(query);
        State.searchResults = results;
        renderTrackList(results, $('search-results'));
    }, 400);
}

// ==========================================
// Now Playing
// ==========================================
function showNowPlaying() {
    if (!State.currentTrack) return;
    $('np-artwork').src = State.currentTrack.artworkUrl100 || '';
    $('np-title').textContent = State.currentTrack.trackName || 'نامشخص';
    $('np-artist').textContent = State.currentTrack.artistName || '';
    $('now-playing').classList.remove('hidden');
    updatePlayButtons();
}

function hideNowPlaying() {
    $('now-playing').classList.add('hidden');
}

// ==========================================
// دوستان
// ==========================================
async function loadFriends() {
    try {
        const [friendsData, requestsData, invitesData] = await Promise.all([
            API.getFriends(),
            API.getRequests(),
            API.getListenInvites(),
        ]);
        State.friends = friendsData.friends;
        State.requests = requestsData.requests;
        State.invites = invitesData.invites;
        renderFriends();
    } catch (err) {
        console.error('Load friends error:', err);
    }
}

function renderFriends() {
    // لیست دوستان
    const list = $('friends-list');
    if (State.friends.length === 0) {
        list.innerHTML = '<p style="color:#888;text-align:center;padding:20px;font-size:13px;">هنوز دوستی نداری</p>';
    } else {
        list.innerHTML = State.friends.map(f => `
            <div class="friend-card">
                <div class="friend-avatar ${f.online ? 'online' : ''}">${f.avatar_emoji}</div>
                <div class="friend-info">
                    <div class="friend-name">${escapeHtml(f.display_name)}</div>
                    <div class="friend-id">@${f.user_id}</div>
                </div>
                <div class="friend-actions">
                    <button class="friend-action-btn" onclick="inviteFriendToListen(${f.user_id})" title="گوش دادن با هم">🎵</button>
                </div>
            </div>
        `).join('');
    }

    // درخواست‌های دریافتی
    const reqList = $('requests-list');
    if (State.requests.length === 0) {
        reqList.innerHTML = '<p style="color:#888;text-align:center;padding:20px;font-size:13px;">درخواستی نیست</p>';
    } else {
        reqList.innerHTML = State.requests.map(r => `
            <div class="friend-card">
                <div class="friend-avatar">${r.avatar_emoji}</div>
                <div class="friend-info">
                    <div class="friend-name">${escapeHtml(r.display_name)}</div>
                    <div class="friend-id">@${r.user_id}</div>
                </div>
                <div class="friend-actions">
                    <button class="friend-action-btn accept" onclick="acceptFriendRequest(${r.user_id})">✓</button>
                </div>
            </div>
        `).join('');
    }

    // دعوت‌های گوش دادن
    const invList = $('invites-list');
    if (State.invites.length === 0) {
        invList.innerHTML = '<p style="color:#888;text-align:center;padding:20px;font-size:13px;">دعوتی نیست</p>';
    } else {
        invList.innerHTML = State.invites.map(inv => `
            <div class="invite-card">
                <div class="invite-header">
                    <span class="invite-avatar">${inv.from_avatar}</span>
                    <div class="invite-info">
                        <div class="invite-from">${escapeHtml(inv.from_user_name)}</div>
                        <div class="invite-text">دعوتت کرده برای گوش دادن با هم</div>
                    </div>
                </div>
                <div class="invite-track">
                    <img src="${inv.track_artwork || ''}" alt="">
                    <div class="invite-track-info">
                        <div class="invite-track-name">${escapeHtml(inv.track_name || '')}</div>
                        <div class="invite-track-artist">${escapeHtml(inv.track_artist || '')}</div>
                    </div>
                </div>
                <div class="invite-buttons">
                    <button class="invite-accept" onclick="acceptListenInvite('${inv.invite_id}')">✓ قبول</button>
                    <button class="invite-reject" onclick="rejectListenInvite('${inv.invite_id}')">✕ رد</button>
                </div>
            </div>
        `).join('');
    }
}

async function acceptFriendRequest(userId) {
    try {
        await API.acceptFriend(userId);
        showToast('✅ دوست شدید!', 'success');
        loadFriends();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

async function acceptListenInvite(inviteId) {
    try {
        const result = await API.acceptListenInvite(inviteId);
        showToast('✅ متصل شدید!', 'success');
        await joinSession(result.session_id);
        loadFriends();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

async function rejectListenInvite(inviteId) {
    try {
        await API.rejectListenInvite(inviteId);
        showToast('رد شد', 'info');
        loadFriends();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

// ==========================================
// افزودن دوست
// ==========================================
function showAddFriendModal() {
    $('modal-add-friend').classList.remove('hidden');
    $('friend-id-input').focus();
}

async function confirmAddFriend() {
    const id = $('friend-id-input').value.trim();
    if (!id) {
        showToast('آیدی رو وارد کن', 'error');
        return;
    }
    try {
        const result = await API.addFriend(parseInt(id));
        showToast('✅ ' + result.message, 'success');
        $('modal-add-friend').classList.add('hidden');
        $('friend-id-input').value = '';
        loadFriends();
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

// ==========================================
// گوش دادن با دوست (Listen Together)
// ==========================================
function showListenWithFriendModal() {
    if (!State.currentTrack) {
        showToast('اول یه موسیقی پخش کن', 'error');
        return;
    }
    if (State.friends.length === 0) {
        showToast('اول دوست اضافه کن', 'error');
        return;
    }

    const list = $('listen-friends-list');
    list.innerHTML = State.friends.map(f => `
        <div class="modal-friend-item" onclick="sendListenInvite(${f.user_id})">
            <span class="modal-friend-avatar">${f.avatar_emoji}</span>
            <div class="modal-friend-info">
                <div class="modal-friend-name">${escapeHtml(f.display_name)}</div>
                <div class="modal-friend-status ${f.online ? 'online' : ''}">
                    ${f.online ? '🟢 آنلاین' : '⚪ آفلاین'}
                </div>
            </div>
        </div>
    `).join('');

    $('modal-listen-with').classList.remove('hidden');
}

async function sendListenInvite(friendId) {
    try {
        await API.sendListenInvite(friendId, State.currentTrack);
        showToast('📨 دعوت ارسال شد! منتظر قبول بمون...', 'success');
        $('modal-listen-with').classList.add('hidden');
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

async function inviteFriendToListen(friendId) {
    if (!State.currentTrack) {
        showToast('اول یه موسیقی پخش کن', 'error');
        return;
    }
    await sendListenInvite(friendId);
}

// ==========================================
// Session (گوش دادن همزمان)
// ==========================================
async function joinSession(sessionId) {
    try {
        const data = await API.getSession(sessionId);
        State.activeSession = data;

        // نمایش صفحه session
        $('main-screen').classList.add('hidden');
        $('session-screen').classList.remove('hidden');

        // اطلاعات track
        const track = {
            trackId: data.track_id,
            trackName: data.track_name,
            artistName: data.track_artist,
            artworkUrl100: data.track_artwork,
            previewUrl: data.track_preview,
        };
        State.currentTrack = track;

        $('session-artwork').src = track.artworkUrl100 || '';
        $('session-track-name').textContent = track.trackName;
        $('session-track-artist').textContent = track.artistName;
        $('session-friend-name').textContent = data.other_user.display_name;
        $('session-friend-avatar').textContent = data.other_user.avatar_emoji;
        $('session-me-avatar').textContent = State.user?.avatar_emoji || '🎵';

        // پخش موسیقی
        State.audio.src = track.previewUrl;
        State.audio.currentTime = data.current_time || 0;
        if (data.is_playing) {
            State.audio.play().catch(() => {});
        }

        // شروع polling برای sync
        startSessionSync();
        startChatPolling();

        showToast('🎧 متصل شدید!', 'success');

    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

function startSessionSync() {
    if (State.syncInterval) clearInterval(State.syncInterval);

    // هر ۳ ثانیه state رو sync کن
    State.syncInterval = setInterval(async () => {
        if (!State.activeSession) return;
        try {
            // ارسال state ما
            await API.updateSession(State.activeSession.session_id, {
                current_time: State.audio.currentTime,
                is_playing: !State.audio.paused,
            });
        } catch (err) {
            console.error('Sync error:', err);
        }
    }, 3000);
}

function startChatPolling() {
    if (State.chatPollInterval) clearInterval(State.chatPollInterval);
    let lastMsgTime = 0;

    const poll = async () => {
        if (!State.activeSession) return;
        try {
            const data = await API.getMessages(State.activeSession.session_id, lastMsgTime);
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(m => {
                    if (m.timestamp > lastMsgTime) lastMsgTime = m.timestamp;
                    appendChatMessage(m);
                });
            }
        } catch (err) {
            console.error('Chat poll error:', err);
        }
    };

    poll(); // بلافاصله یه بار
    State.chatPollInterval = setInterval(poll, 2000);
}

function appendChatMessage(msg) {
    const messages = $('chat-messages');
    const isMe = msg.is_me;
    const html = `
        <div class="chat-message ${isMe ? 'me' : ''}">
            <div class="chat-message-avatar">${msg.avatar_emoji}</div>
            <div>
                ${!isMe ? `<div class="chat-message-name">${escapeHtml(msg.user_name)}</div>` : ''}
                <div class="chat-message-bubble">${escapeHtml(msg.message)}</div>
            </div>
        </div>
    `;
    messages.insertAdjacentHTML('beforeend', html);
    messages.scrollTop = messages.scrollHeight;
}

async function sendChatMessage() {
    const input = $('chat-input');
    const message = input.value.trim();
    if (!message || !State.activeSession) return;

    input.value = '';
    try {
        await API.sendMessage(State.activeSession.session_id, message);
        // پیام ما بلافاصله نمایش داده می‌شه
        appendChatMessage({
            user_name: State.user?.display_name || 'شما',
            avatar_emoji: State.user?.avatar_emoji || '🎵',
            message: message,
            is_me: true,
        });
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

async function leaveSession() {
    if (!State.activeSession) return;
    if (!confirm('از جلسه خارج میشی؟')) return;

    try {
        await API.endSession(State.activeSession.session_id);
    } catch (err) {
        // ignore
    }
    cleanupSession();
    showToast('از جلسه خارج شدی', 'info');
}

function cleanupSession() {
    if (State.syncInterval) clearInterval(State.syncInterval);
    if (State.chatPollInterval) clearInterval(State.chatPollInterval);
    State.activeSession = null;
    State.audio.pause();
    $('session-screen').classList.add('hidden');
    $('main-screen').classList.remove('hidden');
}

async function sessionPlayToggle() {
    if (!State.activeSession) return;
    if (State.audio.paused) {
        State.audio.play();
        $('session-play').textContent = '⏸';
    } else {
        State.audio.pause();
        $('session-play').textContent = '▶';
    }
    // آپدیت فوری state
    try {
        await API.updateSession(State.activeSession.session_id, {
            current_time: State.audio.currentTime,
            is_playing: !State.audio.paused,
        });
    } catch (err) {}
}

async function sessionSync() {
    if (!State.activeSession) return;
    try {
        const data = await API.getSession(State.activeSession.session_id);
        State.audio.currentTime = data.current_time || 0;
        if (data.is_playing && State.audio.paused) {
            State.audio.play();
            $('session-play').textContent = '⏸';
        } else if (!data.is_playing && !State.audio.paused) {
            State.audio.pause();
            $('session-play').textContent = '▶';
        }
        showToast('🔄 همگام‌سازی شد', 'info');
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

// ==========================================
// SSE - دریافت event‌های real-time
// ==========================================
function connectSSE() {
    if (State.eventSource) {
        State.eventSource.close();
    }

    try {
        State.eventSource = new EventSource(`${CONFIG.SIGNALING_URL}/api/events?user_id=${CONFIG.USER_ID}`);

        State.eventSource.addEventListener('hello', (e) => {
            console.log('SSE connected');
        });

        State.eventSource.addEventListener('ping', (e) => {
            // keep-alive
        });

        State.eventSource.addEventListener('friend_request', (e) => {
            const data = JSON.parse(e.data);
            showToast(`📨 ${data.from_user_name} درخواست دوستی فرستاد`, 'info');
            loadFriends();
        });

        State.eventSource.addEventListener('friend_accepted', (e) => {
            showToast('✅ دوست شدید!', 'success');
            loadFriends();
        });

        State.eventSource.addEventListener('listen_invite', (e) => {
            const data = JSON.parse(e.data);
            showToast(`🎵 ${data.from_user_name} دعوتت کرد برای گوش دادن!`, 'info');
            loadFriends();
        });

        State.eventSource.addEventListener('listen_accepted', (e) => {
            const data = JSON.parse(e.data);
            showToast('✅ دعوتت قبول شد!', 'success');
            joinSession(data.session_id);
        });

        State.eventSource.addEventListener('listen_rejected', (e) => {
            showToast('دعوتت رد شد', 'info');
        });

        State.eventSource.addEventListener('session_update', (e) => {
            const data = JSON.parse(e.data);
            handleSessionUpdate(data);
        });

        State.eventSource.addEventListener('session_track_changed', (e) => {
            const data = JSON.parse(e.data);
            handleTrackChange(data);
        });

        State.eventSource.addEventListener('session_message', (e) => {
            const data = JSON.parse(e.data);
            if (State.activeSession && State.activeSession.session_id === data.session_id) {
                // پیام رو نشون بده (ولی اگه از خودمونه، skip)
                if (data.user_id !== CONFIG.USER_ID) {
                    appendChatMessage({
                        user_name: data.user_name,
                        avatar_emoji: data.avatar_emoji,
                        message: data.message,
                        is_me: false,
                    });
                }
            }
        });

        State.eventSource.addEventListener('session_ended', (e) => {
            const data = JSON.parse(e.data);
            if (State.activeSession && State.activeSession.session_id === data.session_id) {
                showToast('جلسه تموم شد', 'info');
                cleanupSession();
            }
        });

        State.eventSource.onerror = (e) => {
            console.error('SSE error');
            // reconnect بعد از ۵ ثانیه
            setTimeout(connectSSE, 5000);
        };
    } catch (err) {
        console.error('SSE connect error:', err);
        setTimeout(connectSSE, 5000);
    }
}

function handleSessionUpdate(data) {
    if (!State.activeSession || State.activeSession.session_id !== data.session_id) return;

    // اگه تغییر زمان زیادی داره، seek کن
    const timeDiff = Math.abs(State.audio.currentTime - data.current_time);
    if (timeDiff > 1.5) {
        State.audio.currentTime = data.current_time;
    }

    // اگه state play/pause عوض شده
    if (data.is_playing && State.audio.paused) {
        State.audio.play().catch(() => {});
        $('session-play').textContent = '⏸';
    } else if (!data.is_playing && !State.audio.paused) {
        State.audio.pause();
        $('session-play').textContent = '▶';
    }
}

function handleTrackChange(data) {
    if (!State.activeSession || State.activeSession.session_id !== data.session_id) return;

    const track = data.track;
    State.currentTrack = track;
    State.audio.src = track.previewUrl;
    State.audio.currentTime = 0;

    $('session-artwork').src = track.artworkUrl100 || '';
    $('session-track-name').textContent = track.trackName;
    $('session-track-artist').textContent = track.artistName;

    showToast('🎵 موسیقی عوض شد', 'info');
}

// ==========================================
// history
// ==========================================
async function loadHistory() {
    try {
        const data = await API.getHistory();
        State.history = data.history;
        renderHistory();
    } catch (err) {
        console.error('Load history error:', err);
    }
}

function renderHistory() {
    const list = $('history-list');
    if (State.history.length === 0) {
        list.innerHTML = `
            <div class="discover-default">
                <div class="empty-art">📜</div>
                <h3>تاریخچه خالیه</h3>
                <p>موسیقی‌هایی که گوش می‌کنی اینجا ذخیره می‌شن</p>
            </div>
        `;
        return;
    }
    renderTrackList(State.history, list);
}

// ==========================================
// پروفایل
// ==========================================
function showProfileModal() {
    if (State.user) {
        $('profile-name').value = State.user.display_name || '';
        $('profile-id').textContent = CONFIG.USER_ID;
        State.selectedEmoji = State.user.avatar_emoji || '🎵';
        // highlight selected emoji
        $$('#emoji-picker button').forEach(b => {
            b.classList.toggle('selected', b.textContent === State.selectedEmoji);
        });
    }
    $('modal-profile').classList.remove('hidden');
}

async function saveProfile() {
    const name = $('profile-name').value.trim();
    if (!name) {
        showToast('نام رو وارد کن', 'error');
        return;
    }
    try {
        await API.updateMe({
            display_name: name,
            avatar_emoji: State.selectedEmoji,
        });
        State.user.display_name = name;
        State.user.avatar_emoji = State.selectedEmoji;
        $('my-avatar').textContent = State.selectedEmoji;
        showToast('✅ ذخیره شد', 'success');
        $('modal-profile').classList.add('hidden');
    } catch (err) {
        showToast('❌ ' + err.message, 'error');
    }
}

// ==========================================
// event listeners
// ==========================================
function setupEventListeners() {
    // سرچ
    $('search-input').addEventListener('input', (e) => {
        handleSearch(e.target.value);
        $('clear-search').classList.toggle('visible', e.target.value.length > 0);
    });
    $('clear-search').addEventListener('click', () => {
        $('search-input').value = '';
        handleSearch('');
        $('clear-search').classList.remove('visible');
    });

    // tag buttons
    $$('.tag-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            $('search-input').value = btn.dataset.tag;
            handleSearch(btn.dataset.tag);
        });
    });

    // tab ها
    $$('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            $$('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            $$('.tab-content').forEach(c => c.classList.remove('active'));
            $(`tab-${tabName}`).classList.add('active');
            State.currentTab = tabName;

            if (tabName === 'history') loadHistory();
            if (tabName === 'friends') loadFriends();
        });
    });

    // player controls
    $('play-btn').addEventListener('click', togglePlay);
    $('player-info').addEventListener('click', showNowPlaying);
    $('np-close').addEventListener('click', hideNowPlaying);
    $('np-play').addEventListener('click', togglePlay);
    $('np-prev').addEventListener('click', () => {
        State.audio.currentTime = 0;
    });
    $('np-next').addEventListener('click', () => {
        State.audio.currentTime = State.duration;
    });

    // listen together
    $('listen-together-btn').addEventListener('click', showListenWithFriendModal);
    $('np-listen-together').addEventListener('click', showListenWithFriendModal);

    // progress bar کلیک
    $('progress-bar').addEventListener('click', (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        State.audio.currentTime = pct * State.duration;
    });
    $('np-progress-bar').addEventListener('click', (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        State.audio.currentTime = pct * State.duration;
    });

    // add friend
    $('add-friend-btn').addEventListener('click', showAddFriendModal);
    $('add-friend-cancel').addEventListener('click', () => {
        $('modal-add-friend').classList.add('hidden');
    });
    $('add-friend-confirm').addEventListener('click', confirmAddFriend);

    // listen with friend modal
    $('listen-cancel').addEventListener('click', () => {
        $('modal-listen-with').classList.add('hidden');
    });

    // profile
    $('profile-btn').addEventListener('click', showProfileModal);
    $('profile-cancel').addEventListener('click', () => {
        $('modal-profile').classList.add('hidden');
    });
    $('profile-save').addEventListener('click', saveProfile);
    $$('#emoji-picker button').forEach(b => {
        b.addEventListener('click', () => {
            $$('#emoji-picker button').forEach(x => x.classList.remove('selected'));
            b.classList.add('selected');
            State.selectedEmoji = b.textContent;
        });
    });

    // session
    $('session-close').addEventListener('click', leaveSession);
    $('session-play').addEventListener('click', sessionPlayToggle);
    $('session-sync').addEventListener('click', sessionSync);
    $('chat-send').addEventListener('click', sendChatMessage);
    $('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendChatMessage();
    });

    // session progress bar کلیک
    document.addEventListener('click', (e) => {
        if (e.target.closest('.session-progress') && State.activeSession) {
            const bar = e.target.closest('.session-progress');
            const rect = bar.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            State.audio.currentTime = pct * State.duration;
            // آپدیت فوری
            sessionPlayToggle().then(() => sessionPlayToggle()); // toggle back
        }
    });
}

// ==========================================
// راه‌اندازی
// ==========================================
async function init() {
    // پنهان کردن لودر
    setTimeout(() => $('loader').classList.add('hidden'), 1500);

    // مقداردهی audio
    initAudio();

    // تنظیم event listener‌ها
    setupEventListeners();

    // راه‌اندازی Telegram WebApp
    if (window.Telegram?.WebApp) {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
    }

    // اتصال به SSE
    connectSSE();

    // گرفتن اطلاعات کاربر
    try {
        const userData = await API.getMe();
        State.user = userData;
        $('my-avatar').textContent = userData.avatar_emoji;
    } catch (err) {
        console.error('Get user error:', err);
        showToast('⚠️ به سرور وصل نشدی. SIGNALING_URL رو در app.js تنظیم کن.', 'error');
    }

    // لود اولیه دوستان
    setTimeout(loadFriends, 2000);
    setInterval(loadFriends, 30000); // refresh هر ۳۰ ثانیه
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
