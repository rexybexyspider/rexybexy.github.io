/* ==========================================
   🎵 ربات موسیقی - نسخه‌ی Audius
   موسیقی‌های کامل (نه preview) - کاملاً رایگان - بدون API key
   ========================================== */

// ==========================================
// تنظیمات Audius
// ==========================================
const CONFIG = {
    APP_NAME: 'mycitybot',
    AUDIUS_API: 'https://api.audius.co',
};

// لیست host های Audius (در صورت خرابی یکی، از دیگری استفاده می‌کنیم)
let AUDIUS_HOSTS = [];
let CURRENT_HOST = '';

// ==========================================
// Storage - مدیریت localStorage
// ==========================================
const Storage = {
    KEYS: {
        USER: 'music_user',
        HISTORY: 'music_history',
        FAVORITES: 'music_favorites',
        HOST: 'audius_host',
    },

    getUser() {
        try { return JSON.parse(localStorage.getItem(this.KEYS.USER)) || null; } catch { return null; }
    },
    setUser(user) { localStorage.setItem(this.KEYS.USER, JSON.stringify(user)); },
    getHistory() {
        try { return JSON.parse(localStorage.getItem(this.KEYS.HISTORY)) || []; } catch { return []; }
    },
    addToHistory(track) {
        const history = this.getHistory();
        const filtered = history.filter(t => t.id !== track.id);
        filtered.unshift({
            id: track.id,
            title: track.title,
            artist: track.user?.name || 'نامشخص',
            artwork: track.artwork?.['480x480'] || track.artwork?.['150x150'] || '',
            duration: track.duration || 0,
            genre: track.genre || '',
            listenedAt: Date.now(),
        });
        localStorage.setItem(this.KEYS.HISTORY, JSON.stringify(filtered.slice(0, 100)));
    },
    clearHistory() { localStorage.removeItem(this.KEYS.HISTORY); },
    getFavorites() {
        try { return JSON.parse(localStorage.getItem(this.KEYS.FAVORITES)) || []; } catch { return []; }
    },
    toggleFavorite(track) {
        const favorites = this.getFavorites();
        const index = favorites.findIndex(t => t.id === track.id);
        if (index >= 0) {
            favorites.splice(index, 1);
            localStorage.setItem(this.KEYS.FAVORITES, JSON.stringify(favorites));
            return false;
        } else {
            favorites.unshift({
                id: track.id,
                title: track.title,
                artist: track.user?.name || 'نامشخص',
                artwork: track.artwork?.['480x480'] || track.artwork?.['150x150'] || '',
                duration: track.duration || 0,
                genre: track.genre || '',
                addedAt: Date.now(),
            });
            localStorage.setItem(this.KEYS.FAVORITES, JSON.stringify(favorites));
            return true;
        }
    },
    isFavorite(trackId) {
        return this.getFavorites().some(t => t.id === trackId);
    },
    getHost() { return localStorage.getItem(this.KEYS.HOST) || ''; },
    setHost(host) { localStorage.setItem(this.KEYS.HOST, host); },
};

// ==========================================
// State
// ==========================================
const State = {
    user: null,
    searchResults: [],
    trending: [],
    history: [],
    favorites: [],
    currentTrack: null,
    isPlaying: false,
    currentTime: 0,
    duration: 0,
    audio: null,
    selectedEmoji: '🎵',
    currentTab: 'discover',
    currentTrackList: [],
    currentIndex: -1,
};

// ==========================================
// ابزارها
// ==========================================
function $(id) { return document.getElementById(id); }
function $$(sel) { return document.querySelectorAll(sel); }

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
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
// Audius API
// ==========================================
async function initAudius() {
    // اول از host ذخیره‌شده استفاده کن
    const savedHost = Storage.getHost();
    if (savedHost) {
        CURRENT_HOST = savedHost;
        return;
    }

    try {
        const resp = await fetch(`${CONFIG.AUDIUS_API}/v1/hosts`);
        const data = await resp.json();
        if (data.data && data.data.length > 0) {
            AUDIUS_HOSTS = data.data.slice(0, 5); // ۵ تا host اول
            CURRENT_HOST = AUDIUS_HOSTS[0];
            Storage.setHost(CURRENT_HOST);
        } else {
            // fallback به host مستقیم
            CURRENT_HOST = 'https://api.audius.co';
        }
    } catch (err) {
        console.error('Audius init error:', err);
        CURRENT_HOST = 'https://api.audius.co';
    }
}

async function tryFetch(path) {
    // اگه host فعلی کار نکرد، از بقیه استفاده کن
    const hostsToTry = [CURRENT_HOST, ...AUDIUS_HOSTS.filter(h => h !== CURRENT_HOST)];
    if (hostsToTry.length === 0) hostsToTry.push('https://api.audius.co');

    for (const host of hostsToTry) {
        try {
            const url = `${host}${path}${path.includes('?') ? '&' : '?'}app_name=${CONFIG.APP_NAME}`;
            const resp = await fetch(url);
            if (resp.ok) {
                if (host !== CURRENT_HOST) {
                    CURRENT_HOST = host;
                    Storage.setHost(host);
                }
                return await resp.json();
            }
        } catch (err) {
            console.warn(`Host ${host} failed:`, err);
        }
    }
    throw new Error('همه‌ی host‌های Audius ناموفق بودن');
}

async function searchMusic(query) {
    if (!query.trim()) return [];
    if (!CURRENT_HOST) await initAudius();

    try {
        const data = await tryFetch(`/v1/tracks/search?query=${encodeURIComponent(query)}&limit=30`);
        return data.data || [];
    } catch (err) {
        console.error('Search error:', err);
        showToast('خطا در سرچ. دوباره امتحان کن.', 'error');
        return [];
    }
}

async function getTrending() {
    if (!CURRENT_HOST) await initAudius();

    try {
        const data = await tryFetch('/v1/tracks/trending?time=week&limit=30');
        return data.data || [];
    } catch (err) {
        console.error('Trending error:', err);
        return [];
    }
}

function getStreamUrl(trackId) {
    return `${CURRENT_HOST}/v1/tracks/${trackId}/stream?app_name=${CONFIG.APP_NAME}`;
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
    });

    State.audio.addEventListener('ended', () => {
        State.isPlaying = false;
        updatePlayButtons();
        playNext();
    });

    State.audio.addEventListener('play', () => {
        State.isPlaying = true;
        updatePlayButtons();
    });

    State.audio.addEventListener('pause', () => {
        State.isPlaying = false;
        updatePlayButtons();
    });

    State.audio.addEventListener('loadedmetadata', () => {
        State.duration = State.audio.duration || 0;
        $('total-time').textContent = formatTime(State.duration);
        $('np-total').textContent = formatTime(State.duration);
    });

    State.audio.addEventListener('error', (e) => {
        console.error('Audio error:', e);
        showToast('خطا در پخش. موسیقی ممکنه در دسترس نباشه.', 'error');
    });

    State.audio.addEventListener('loading', () => {
        showToast('⏳ در حال بارگذاری موسیقی...', 'info');
    });
}

function playTrack(track, list = null, index = null) {
    if (!track.id) {
        showToast('موسیقی نامعتبره', 'error');
        return;
    }

    if (list !== null) {
        State.currentTrackList = list;
        State.currentIndex = list.findIndex(t => t.id === track.id);
    } else if (State.currentIndex === -1) {
        State.currentTrackList = [track];
        State.currentIndex = 0;
    }

    State.currentTrack = track;
    State.audio.src = getStreamUrl(track.id);
    State.audio.play().catch(err => {
        console.error('Play error:', err);
        showToast('نتونستم پخش کنم. ممکنه موسیقی در دسترس نباشه.', 'error');
    });

    showPlayerBar(track);
    showNowPlaying();
    Storage.addToHistory(track);
    State.history = Storage.getHistory();
    updateTrackListHighlight(track);
    updateFavoriteButton();
}

function togglePlay() {
    if (!State.currentTrack) return;
    if (State.audio.paused) {
        State.audio.play();
    } else {
        State.audio.pause();
    }
}

function playNext() {
    if (State.currentTrackList.length === 0) return;
    const nextIndex = (State.currentIndex + 1) % State.currentTrackList.length;
    playTrack(State.currentTrackList[nextIndex]);
}

function playPrev() {
    if (State.currentTrackList.length === 0) return;
    const prevIndex = (State.currentIndex - 1 + State.currentTrackList.length) % State.currentTrackList.length;
    playTrack(State.currentTrackList[prevIndex]);
}

function updatePlayButtons() {
    const playBtn = $('play-btn');
    const npPlay = $('np-play');
    const icon = State.isPlaying ? '⏸' : '▶';
    if (playBtn) playBtn.textContent = icon;
    if (npPlay) npPlay.textContent = icon;

    $$('.track-item').forEach(item => {
        const indicator = item.querySelector('.track-playing-indicator');
        if (indicator) indicator.style.opacity = State.isPlaying ? '1' : '0.3';
    });

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
    $('player-bar').classList.remove('hidden');
    $('player-artwork').src = track.artwork?.['150x150'] || '';
    $('player-title').textContent = track.title || 'نامشخص';
    $('player-artist').textContent = track.user?.name || '';
}

function updatePlayerProgress() {
    if (!State.currentTrack) return;
    const pct = (State.currentTime / (State.duration || 1)) * 100;
    $('progress-fill').style.width = pct + '%';
    $('current-time').textContent = formatTime(State.currentTime);
}

function updateNowPlayingProgress() {
    if (!State.currentTrack) return;
    const pct = (State.currentTime / (State.duration || 1)) * 100;
    $('np-progress-fill').style.width = pct + '%';
    $('np-current').textContent = formatTime(State.currentTime);
}

function updateTrackListHighlight(track) {
    $$('.track-item').forEach(item => {
        item.classList.remove('playing');
        if (item.dataset.trackId === track.id) {
            item.classList.add('playing');
        }
    });
}

function updateFavoriteButton() {
    if (!State.currentTrack) return;
    const isFav = Storage.isFavorite(State.currentTrack.id);
    const btn = $('np-favorite');
    if (btn) {
        if (isFav) {
            btn.classList.add('active');
            btn.textContent = '⭐ در علاقه‌مندی';
        } else {
            btn.classList.remove('active');
            btn.textContent = '⭐ علاقه‌مندی';
        }
    }
}

// ==========================================
// رندر لیست آهنگ‌ها
// ==========================================
function renderTrackList(tracks, container, source = 'search') {
    if (!tracks || tracks.length === 0) {
        let emptyHtml = '';
        if (source === 'history') {
            emptyHtml = `
                <div class="empty-history">
                    <div class="empty-art">📜</div>
                    <h3>تاریخچه خالیه</h3>
                    <p>موسیقی‌هایی که گوش می‌کنی اینجا ذخیره می‌شن</p>
                </div>
            `;
        } else if (source === 'favorites') {
            emptyHtml = `
                <div class="empty-history">
                    <div class="empty-art">⭐</div>
                    <h3>علاقه‌مندی خالیه</h3>
                    <p>موسیقی‌های مورد علاقه‌ات رو اینجا نشون می‌ده</p>
                </div>
            `;
        } else {
            emptyHtml = `
                <div class="discover-default">
                    <div class="empty-art">🔇</div>
                    <h3>چیزی پیدا نشد</h3>
                    <p>یه چیز دیگه سرچ کن</p>
                </div>
            `;
        }
        container.innerHTML = emptyHtml;
        return;
    }

    container.innerHTML = tracks.map((t, i) => {
        const isPlaying = State.currentTrack && State.currentTrack.id === t.id;
        const isFav = Storage.isFavorite(t.id);
        const playingHtml = isPlaying && State.isPlaying
            ? `<div class="track-playing-indicator"><span></span><span></span><span></span></div>`
            : '';
        const artwork = t.artwork?.['150x150'] || '';
        const title = escapeHtml(t.title || 'نامشخص');
        const artist = escapeHtml(t.user?.name || '');
        const genre = t.genre ? `<div class="track-genre">${escapeHtml(t.genre)}</div>` : '';
        const duration = t.duration ? `<span class="track-duration">${formatTime(t.duration)}</span>` : '';

        return `
            <div class="track-item ${isPlaying ? 'playing' : ''}" data-track-id="${t.id}">
                <span class="source-badge">AUDIUS</span>
                <img class="track-artwork" src="${artwork}" alt="" loading="lazy"
                     onerror="this.style.background='var(--bg-mid)';this.src='';">
                <div class="track-info">
                    <div class="track-name">${title}</div>
                    <div class="track-artist">${artist}</div>
                    ${genre}
                </div>
                <div class="track-actions">
                    ${duration}
                    ${playingHtml}
                    <button class="track-action-btn favorite-btn ${isFav ? 'active' : ''}" data-track-id="${t.id}">${isFav ? '⭐' : '☆'}</button>
                    <button class="track-action-btn play-track">▶</button>
                </div>
            </div>
        `;
    }).join('');

    // event listener برای play
    container.querySelectorAll('.track-item').forEach(item => {
        item.onclick = (e) => {
            if (e.target.classList.contains('favorite-btn')) return;
            const trackId = item.dataset.trackId;
            const track = tracks.find(t => t.id === trackId);
            if (track) playTrack(track, tracks);
        };
    });

    // event listener برای favorite
    container.querySelectorAll('.favorite-btn').forEach(btn => {
        btn.onclick = (e) => {
            e.stopPropagation();
            const trackId = btn.dataset.trackId;
            const track = tracks.find(t => t.id === trackId);
            if (track) {
                const added = Storage.toggleFavorite(track);
                State.favorites = Storage.getFavorites();
                showToast(added ? '⭐ به علاقه‌مندی اضافه شد' : 'از علاقه‌مندی حذف شد', 'success');
                btn.textContent = added ? '⭐' : '☆';
                btn.classList.toggle('active', added);
                if (State.currentTab === 'favorites') renderFavorites();
            }
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
    $('search-results').innerHTML = `
        <div class="search-loading">
            <div class="search-loading-spinner"></div>
            <span>🔍 در حال سرچ در Audius...</span>
        </div>
    `;

    searchTimeout = setTimeout(async () => {
        const results = await searchMusic(query);
        State.searchResults = results;
        renderTrackList(results, $('search-results'), 'search');
    }, 400);
}

// ==========================================
// ترند
// ==========================================
async function loadTrending() {
    const list = $('trending-list');
    list.innerHTML = `
        <div class="search-loading">
            <div class="search-loading-spinner"></div>
            <span>🔥 در حال بارگذاری ترندها...</span>
        </div>
    `;
    const trending = await getTrending();
    State.trending = trending;
    renderTrackList(trending, list, 'search');
}

// ==========================================
// Now Playing
// ==========================================
function showNowPlaying() {
    if (!State.currentTrack) return;
    const t = State.currentTrack;
    $('np-artwork').src = t.artwork?.['480x480'] || t.artwork?.['150x150'] || '';
    $('np-title').textContent = t.title || 'نامشخص';
    $('np-artist').textContent = t.user?.name || '';
    $('np-genre').textContent = t.genre ? `🎵 ${t.genre}` : '';
    $('now-playing').classList.remove('hidden');
    updatePlayButtons();
    updateFavoriteButton();
}

function hideNowPlaying() {
    $('now-playing').classList.add('hidden');
}

// ==========================================
// تاریخچه و علاقه‌مندی
// ==========================================
function renderHistory() {
    State.history = Storage.getHistory();
    // تبدیل به فرمت قابل استفاده
    const tracks = State.history.map(t => ({
        id: t.id,
        title: t.title,
        user: { name: t.artist },
        artwork: { '150x150': t.artwork, '480x480': t.artwork },
        duration: t.duration,
        genre: t.genre,
    }));
    renderTrackList(tracks, $('history-list'), 'history');
}

function renderFavorites() {
    State.favorites = Storage.getFavorites();
    const tracks = State.favorites.map(t => ({
        id: t.id,
        title: t.title,
        user: { name: t.artist },
        artwork: { '150x150': t.artwork, '480x480': t.artwork },
        duration: t.duration,
        genre: t.genre,
    }));
    renderTrackList(tracks, $('favorites-list'), 'favorites');
}

// ==========================================
// اشتراک‌گذاری و دانلود
// ==========================================
async function shareTrack() {
    if (!State.currentTrack) return;
    const t = State.currentTrack;
    const text = `🎵 ${t.title} - ${t.user?.name}\n\nگوش بده توی ربات موسیقی!`;

    if (window.Telegram?.WebApp) {
        const url = `https://t.me/share/url?url=${encodeURIComponent(getStreamUrl(t.id))}&text=${encodeURIComponent(text)}`;
        window.open(url, '_blank');
    } else if (navigator.share) {
        try {
            await navigator.share({ title: t.title, text: text });
        } catch (err) {}
    } else {
        try {
            await navigator.clipboard.writeText(text);
            showToast('کپی شد!', 'success');
        } catch (err) {
            showToast('نتونستم کپی کنم', 'error');
        }
    }
}

function downloadTrack() {
    if (!State.currentTrack) return;
    const t = State.currentTrack;
    const url = getStreamUrl(t.id);

    // ایجاد لینک دانلود
    const a = document.createElement('a');
    a.href = url;
    a.download = `${t.title} - ${t.user?.name}.mp3`;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('⬇ دانلود شروع شد', 'success');
}

// ==========================================
// پروفایل
// ==========================================
function showProfileModal() {
    if (State.user) {
        $('profile-name').value = State.user.display_name || '';
        State.selectedEmoji = State.user.avatar_emoji || '🎵';
        $$('#emoji-picker button').forEach(b => {
            b.classList.toggle('selected', b.textContent === State.selectedEmoji);
        });
    }
    $('modal-profile').classList.remove('hidden');
}

function saveProfile() {
    const name = $('profile-name').value.trim();
    if (!name) {
        showToast('نام رو وارد کن', 'error');
        return;
    }
    State.user = { display_name: name, avatar_emoji: State.selectedEmoji };
    Storage.setUser(State.user);
    $('my-avatar').textContent = State.selectedEmoji;
    showToast('✅ ذخیره شد', 'success');
    $('modal-profile').classList.add('hidden');
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
            $('clear-search').classList.add('visible');
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

            if (tabName === 'history') renderHistory();
            if (tabName === 'favorites') renderFavorites();
            if (tabName === 'trending' && State.trending.length === 0) loadTrending();
        });
    });

    // player controls
    $('play-btn').addEventListener('click', togglePlay);
    $('player-info').addEventListener('click', showNowPlaying);
    $('np-close').addEventListener('click', hideNowPlaying);
    $('np-play').addEventListener('click', togglePlay);
    $('np-prev').addEventListener('click', playPrev);
    $('np-next').addEventListener('click', playNext);
    $('prev-btn').addEventListener('click', playPrev);
    $('next-btn').addEventListener('click', playNext);

    // favorite و share و download
    $('np-favorite').addEventListener('click', () => {
        if (!State.currentTrack) return;
        const added = Storage.toggleFavorite(State.currentTrack);
        State.favorites = Storage.getFavorites();
        showToast(added ? '⭐ اضافه شد' : 'حذف شد', 'success');
        updateFavoriteButton();
    });
    $('np-share').addEventListener('click', shareTrack);
    $('np-download').addEventListener('click', downloadTrack);

    // progress bar کلیک
    $('progress-bar').addEventListener('click', (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        if (State.duration) State.audio.currentTime = pct * State.duration;
    });
    $('np-progress-bar').addEventListener('click', (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = (e.clientX - rect.left) / rect.width;
        if (State.duration) State.audio.currentTime = pct * State.duration;
    });

    // profile
    $('profile-btn').addEventListener('click', showProfileModal);
    $('profile-cancel').addEventListener('click', () => $('modal-profile').classList.add('hidden'));
    $('profile-save').addEventListener('click', saveProfile);
    $$('#emoji-picker button').forEach(b => {
        b.addEventListener('click', () => {
            $$('#emoji-picker button').forEach(x => x.classList.remove('selected'));
            b.classList.add('selected');
            State.selectedEmoji = b.textContent;
        });
    });

    // keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT') return;
        if (e.code === 'Space') { e.preventDefault(); togglePlay(); }
        else if (e.code === 'ArrowRight') playPrev();
        else if (e.code === 'ArrowLeft') playNext();
    });
}

// ==========================================
// راه‌اندازی
// ==========================================
async function init() {
    setTimeout(() => $('loader').classList.add('hidden'), 1500);

    initAudio();
    setupEventListeners();

    // راه‌اندازی Telegram WebApp
    if (window.Telegram?.WebApp) {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
        Telegram.WebApp.setHeaderColor('#0a0a1a');
        Telegram.WebApp.setBackgroundColor('#0a0a1a');
    }

    // لود پروفایل
    State.user = Storage.getUser();
    if (State.user) {
        $('my-avatar').textContent = State.user.avatar_emoji || '🎵';
    } else {
        const defaultUser = { display_name: 'کاربر', avatar_emoji: '🎵' };
        State.user = defaultUser;
        Storage.setUser(defaultUser);
    }

    // اتصال به Audius
    await initAudius();
    console.log('✅ متصل به Audius:', CURRENT_HOST);

    // لود history و favorites
    State.history = Storage.getHistory();
    State.favorites = Storage.getFavorites();

    console.log('🎵 موسیقی آماده است!');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
