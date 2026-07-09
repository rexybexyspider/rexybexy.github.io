/* ==========================================
   🏙️ ربات شهر من - نسخه‌ی GitHub Pages
   ذخیره‌سازی در localStorage - نیازی به سرور نیست
   ========================================== */

// ==========================================
// پیکربندی بازی
// ==========================================
const CONFIG = {
    INITIAL_RESOURCES: {
        gold: 500, wood: 300, stone: 200, food: 400, population: 10,
    },
    INITIAL_POP_CAP: 50,
    RESOURCE_RATES: { gold: 5, wood: 8, stone: 6, food: 10 },
    POP_GROWTH_RATE: 2,
    ATTACK_COST: 50,
    SOLDIER_STRENGTH: 10,
    UPGRADE_MULTIPLIER: 1.5,
};

const BUILDINGS = {
    house:        { name: '🏠 خانه',        desc: 'افزایش ظرفیت جمعیت', cost: { gold: 100, wood: 150, stone: 50  }, effect: { pop_cap: 10 } },
    farm:         { name: '🌾 مزرعه',       desc: 'تولید غذا',          cost: { gold: 80,  wood: 100, stone: 30  }, effect: { food_rate: 10 } },
    lumber_mill:  { name: '🪵 چوب‌بری',    desc: 'تولید چوب',          cost: { gold: 100, wood: 50,  stone: 80  }, effect: { wood_rate: 8 } },
    quarry:       { name: '⛏️ معدن سنگ',   desc: 'تولید سنگ',          cost: { gold: 120, wood: 80,  stone: 40  }, effect: { stone_rate: 6 } },
    market:       { name: '🏪 بازار',       desc: 'تولید طلا (مالیات)', cost: { gold: 200, wood: 150, stone: 100 }, effect: { gold_rate: 5 } },
    barracks:     { name: '⚔️ سربازخانه',  desc: 'آموزش سرباز',         cost: { gold: 300, wood: 200, stone: 150 }, effect: { soldier_cap: 20 } },
    wall:         { name: '🛡️ دیوار دفاعی',desc: 'افزایش دفاع شهر',    cost: { gold: 150, wood: 50,  stone: 200 }, effect: { defense: 15 } },
    castle:       { name: '🏰 قلعه',         desc: 'نماد قدرت - ارتقا',  cost: { gold: 1000, wood: 800, stone: 600 }, effect: { level_up: true } },
};

const BUILDING_ART = {
    house:       { emoji: '🏠' },
    farm:        { emoji: '🌾' },
    lumber_mill: { emoji: '🪵' },
    quarry:      { emoji: '⛏️' },
    market:      { emoji: '🏪' },
    barracks:    { emoji: '⚔️' },
    wall:        { emoji: '🛡️' },
    castle:      { emoji: '🏰' },
};

const CITY_NAMES_PREFIX = ['شهر', 'دژ', 'قلعه', 'استان', 'پایتخت'];
const CITY_NAMES_SUFFIX = ['آرا', 'دین', 'شهر', 'ستان', 'آباد', 'گل', 'مهر', 'نور', 'بوم', 'زار'];

// ==========================================
// ذخیره‌سازی
// ==========================================
const Storage = {
    KEY: 'my_city_bot_data_v1',

    load() {
        try {
            const raw = localStorage.getItem(this.KEY);
            return raw ? JSON.parse(raw) : null;
        } catch (e) {
            console.error('Load error:', e);
            return null;
        }
    },

    save(data) {
        try {
            localStorage.setItem(this.KEY, JSON.stringify(data));
            return true;
        } catch (e) {
            console.error('Save error:', e);
            return false;
        }
    },

    clear() {
        localStorage.removeItem(this.KEY);
    },
};

// ==========================================
// State
// ==========================================
let State = {
    city: null,
    buildings: [],
    friends: [],
    lastSave: Date.now(),
    selectedTrainAmount: 1,
    selectedTradeFriend: null,
    autoTimer: null,
};

// ==========================================
// ابزارهای کمکی
// ==========================================
function $(id) { return document.getElementById(id); }
function $$(sel) { return document.querySelectorAll(sel); }

function faNum(n) {
    return Number(n).toLocaleString('fa-IR');
}

function showToast(message, type = '') {
    const toast = $('toast');
    toast.textContent = message;
    toast.className = 'toast ' + type;
    setTimeout(() => toast.classList.add('hidden'), 2500);
}

function showConfirm(title, message, onConfirm) {
    $('confirm-title').textContent = title;
    $('confirm-message').textContent = message;
    $('confirm-modal').classList.remove('hidden');
    $('confirm-yes').onclick = () => {
        $('confirm-modal').classList.add('hidden');
        onConfirm();
    };
    $('confirm-no').onclick = () => {
        $('confirm-modal').classList.add('hidden');
    };
}

function randInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function randChoice(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
}

function generateCityName() {
    return randChoice(CITY_NAMES_PREFIX) + randChoice(CITY_NAMES_SUFFIX);
}

// ==========================================
// منطق بازی
// ==========================================
function calculateProduction() {
    const rates = { gold: 0, wood: 0, stone: 0, food: 0 };
    State.buildings.forEach(b => {
        const mult = b.level * b.count;
        if (b.type === 'market')      rates.gold  += CONFIG.RESOURCE_RATES.gold  * mult;
        if (b.type === 'lumber_mill') rates.wood  += CONFIG.RESOURCE_RATES.wood  * mult;
        if (b.type === 'quarry')      rates.stone += CONFIG.RESOURCE_RATES.stone * mult;
        if (b.type === 'farm')        rates.food  += CONFIG.RESOURCE_RATES.food  * mult;
    });
    return rates;
}

function calculatePopCap() {
    let cap = CONFIG.INITIAL_POP_CAP;
    State.buildings.forEach(b => {
        if (b.type === 'house') cap += 10 * b.level * b.count;
    });
    return cap;
}

function calculateDefense() {
    let defense = 0;
    State.buildings.forEach(b => {
        if (b.type === 'wall') defense += b.count * b.level * 15;
    });
    defense += State.city.soldiers * 10;
    return defense;
}

function calculateScore() {
    const city = State.city;
    const buildingScore = State.buildings.reduce((s, b) => s + b.count * b.level * 10, 0);
    const resourceScore = Math.floor((city.gold + city.wood + city.stone + city.food) / 10);
    const popScore = city.population * 5;
    const soldierScore = city.soldiers * 8;
    const levelScore = city.city_level * 100;
    return buildingScore + resourceScore + popScore + soldierScore + levelScore;
}

// ==========================================
// زمان و تولید
// ==========================================
function collectResources() {
    const now = Date.now();
    const hours = (now - State.lastSave) / 3600000;
    if (hours < 0.05) return { gold: 0, wood: 0, stone: 0, food: 0, hours: 0 };

    const rates = calculateProduction();
    const produced = {
        gold:  Math.floor(rates.gold  * hours),
        wood:  Math.floor(rates.wood  * hours),
        stone: Math.floor(rates.stone * hours),
        food:  Math.floor(rates.food  * hours),
    };

    State.city.gold  += produced.gold;
    State.city.wood  += produced.wood;
    State.city.stone += produced.stone;
    State.city.food  += produced.food;

    // رشد جمعیت
    const cap = calculatePopCap();
    if (State.city.population < cap) {
        const growth = Math.floor(CONFIG.POP_GROWTH_RATE * hours);
        State.city.population = Math.min(cap, State.city.population + growth);
        produced.pop_growth = Math.min(cap, State.city.population + growth) - (State.city.population - growth);
    }
    State.city.pop_cap = cap;

    State.lastSave = now;
    saveGame();
    return produced;
}

// ==========================================
// ساختمان‌ها
// ==========================================
function canBuild(type) {
    const b = BUILDINGS[type];
    if (!b) return { ok: false, msg: 'نوع نامعتبر' };
    for (const [res, amt] of Object.entries(b.cost)) {
        if (State.city[res] < amt) {
            const fa = { gold: 'طلا', wood: 'چوب', stone: 'سنگ', food: 'غذا' }[res];
            return { ok: false, msg: `❌ ${fa} کافی نیست (${faNum(State.city[res])}/${faNum(amt)})` };
        }
    }
    return { ok: true };
}

function buildBuilding(type) {
    const check = canBuild(type);
    if (!check.ok) return { ok: false, msg: check.msg };

    const b = BUILDINGS[type];
    for (const [res, amt] of Object.entries(b.cost)) {
        State.city[res] -= amt;
    }

    const existing = State.buildings.find(x => x.type === type);
    if (existing) {
        existing.count += 1;
    } else {
        State.buildings.push({ type, level: 1, count: 1 });
    }

    if (type === 'castle') {
        State.city.city_level += 1;
    }

    saveGame();
    return { ok: true, msg: `✅ ${b.name} ساخته شد!` };
}

function getUpgradeCost(type) {
    const b = State.buildings.find(x => x.type === type);
    if (!b) return null;
    const base = BUILDINGS[type].cost;
    const mult = CONFIG.UPGRADE_MULTIPLIER * b.level;
    const cost = {};
    for (const [res, amt] of Object.entries(base)) {
        cost[res] = Math.floor(amt * mult);
    }
    return cost;
}

function upgradeBuilding(type) {
    const b = State.buildings.find(x => x.type === type);
    if (!b) return { ok: false, msg: 'این ساختمان رو نساختی' };

    const cost = getUpgradeCost(type);
    for (const [res, amt] of Object.entries(cost)) {
        if (State.city[res] < amt) {
            const fa = { gold: 'طلا', wood: 'چوب', stone: 'سنگ', food: 'غذا' }[res];
            return { ok: false, msg: `❌ ${fa} کافی نیست (${faNum(State.city[res])}/${faNum(amt)})` };
        }
    }
    for (const [res, amt] of Object.entries(cost)) {
        State.city[res] -= amt;
    }
    b.level += 1;
    saveGame();
    return { ok: true, msg: `✅ ${BUILDINGS[type].name} به سطح ${b.level} ارتقا یافت!` };
}

// ==========================================
// ارتش
// ==========================================
function trainSoldiers(count) {
    const barracks = State.buildings.find(b => b.type === 'barracks');
    if (!barracks) return { ok: false, msg: '❌ اول سربازخانه بساز' };

    const cap = 20 * barracks.level * barracks.count;
    if (State.city.soldiers + count > cap) {
        return { ok: false, msg: `❌ ظرفیت پره (max: ${faNum(cap)})` };
    }

    const goldCost = 50 * count;
    const foodCost = 30 * count;
    if (State.city.gold < goldCost) return { ok: false, msg: `❌ طلا کافی نیست (${faNum(State.city.gold)}/${faNum(goldCost)})` };
    if (State.city.food < foodCost) return { ok: false, msg: `❌ غذا کافی نیست (${faNum(State.city.food)}/${faNum(foodCost)})` };

    State.city.gold -= goldCost;
    State.city.food -= foodCost;
    State.city.soldiers += count;
    saveGame();
    return { ok: true, msg: `✅ ${faNum(count)} سرباز آموزش یافتند!` };
}

// ==========================================
// دوستان
// ==========================================
function addFriend(telegramId, name) {
    const friend = State.friends.find(f => f.user_id === telegramId);
    if (friend) return { ok: false, msg: 'این دوست قبلاً اضافه شده' };

    const newFriend = {
        user_id: telegramId,
        name: name || generateCityName(),
        gold: 500, wood: 300, stone: 200, food: 400,
        population: 10, pop_cap: 50,
        soldiers: 0, defense: 0,
        city_level: 1,
        buildings: [{ type: 'house', level: 1, count: 1 }],
        last_growth: Date.now(),
    };
    State.friends.push(newFriend);
    saveGame();
    return { ok: true, msg: `✅ دوست اضافه شد: ${newFriend.name}`, friend: newFriend };
}

function removeFriend(friendId) {
    State.friends = State.friends.filter(f => f.user_id !== friendId);
    saveGame();
}

function getFriendScore(friend) {
    const buildingScore = friend.buildings.reduce((s, b) => s + b.count * b.level * 10, 0);
    const resourceScore = Math.floor((friend.gold + friend.wood + friend.stone + friend.food) / 10);
    const popScore = friend.population * 5;
    const soldierScore = friend.soldiers * 8;
    const levelScore = friend.city_level * 100;
    return buildingScore + resourceScore + popScore + soldierScore + levelScore;
}

function growFriend(friend) {
    // شبیه‌سازی رشد یک ساعته
    friend.buildings.forEach(b => {
        const mult = b.level * b.count;
        if (b.type === 'market')      friend.gold  += 5  * mult;
        if (b.type === 'lumber_mill') friend.wood  += 8  * mult;
        if (b.type === 'quarry')      friend.stone += 6  * mult;
        if (b.type === 'farm')        friend.food  += 10 * mult;
    });

    const cap = friend.buildings.reduce((s, b) => b.type === 'house' ? s + 10 * b.level * b.count : s, 50);
    if (friend.population < cap) {
        friend.population = Math.min(cap, friend.population + randInt(1, 5));
    }
    friend.pop_cap = cap;

    // ۳۰٪ شانس ساخت ساختمان جدید
    if (Math.random() < 0.3 && friend.buildings.reduce((s, b) => s + b.count, 0) < 20) {
        const types = ['house', 'farm', 'lumber_mill', 'quarry', 'market'];
        const type = randChoice(types);
        const existing = friend.buildings.find(b => b.type === type);
        if (existing) existing.count += 1;
        else friend.buildings.push({ type, level: 1, count: 1 });
    }

    // ۲۰٪ شانس آموزش سرباز
    if (Math.random() < 0.2 && friend.gold > 200 && friend.food > 100) {
        friend.gold -= 100;
        friend.food -= 60;
        friend.soldiers += 2;
    }

    // محاسبه‌ی دفاع
    let defense = 0;
    friend.buildings.forEach(b => {
        if (b.type === 'wall') defense += b.count * b.level * 15;
    });
    defense += friend.soldiers * 10;
    friend.defense = defense;

    friend.last_growth = Date.now();
}

function growAllFriends() {
    const now = Date.now();
    State.friends.forEach(f => {
        const hoursPassed = (now - f.last_growth) / 3600000;
        if (hoursPassed >= 1) {
            const cycles = Math.floor(hoursPassed);
            for (let i = 0; i < cycles; i++) growFriend(f);
        }
    });
    saveGame();
}

// ==========================================
// نبرد
// ==========================================
function attackCity(friendId, soldiersToSend) {
    const friend = State.friends.find(f => f.user_id === friendId);
    if (!friend) return { ok: false, msg: 'دوست پیدا نشد' };
    if (State.city.gold < CONFIG.ATTACK_COST) return { ok: false, msg: `❌ طلا کافی نیست (نیاز: ${faNum(CONFIG.ATTACK_COST)})` };
    if (soldiersToSend > State.city.soldiers) return { ok: false, msg: `❌ سرباز کافی نداری (${faNum(State.city.soldiers)}/${faNum(soldiersToSend)})` };
    if (soldiersToSend <= 0) return { ok: false, msg: 'حداقل ۱ سرباز بفرست' };

    const attackPower = soldiersToSend * CONFIG.SOLDIER_STRENGTH;
    const defensePower = friend.defense || (friend.soldiers * 10);

    let result;
    if (attackPower > defensePower) {
        // پیروزی
        const lootRatio = Math.min(0.3, (attackPower - defensePower) / Math.max(1, attackPower));
        const goldLoot = Math.floor(friend.gold * lootRatio);
        const foodLoot = Math.floor(friend.food * lootRatio * 0.5);
        const losses = Math.floor(soldiersToSend * (Math.random() * 0.2 + 0.2));
        const remaining = soldiersToSend - losses;
        const defenderLosses = Math.floor(friend.soldiers * (Math.random() * 0.3 + 0.5));

        State.city.gold = State.city.gold - CONFIG.ATTACK_COST + goldLoot;
        State.city.food = State.city.food + foodLoot;
        State.city.soldiers = State.city.soldiers - soldiersToSend + remaining;
        friend.gold -= goldLoot;
        friend.food -= foodLoot;
        friend.soldiers = Math.max(0, friend.soldiers - defenderLosses);

        result = {
            ok: true, victory: true,
            msg: `🏆 **پیروزی!**\n\n⚔️ سرباز ارسالی: ${faNum(soldiersToSend)}\n💀 تلفات شما: ${faNum(losses)}\n🪙 غنیمت طلا: ${faNum(goldLoot)}\n🌾 غنیمت غذا: ${faNum(foodLoot)}\n🛡️ تلفات دشمن: ${faNum(defenderLosses)} سرباز`,
        };
    } else {
        // شکست
        const losses = Math.floor(soldiersToSend * (Math.random() * 0.3 + 0.6));
        const remaining = soldiersToSend - losses;
        const defenderLosses = Math.floor(friend.soldiers * (Math.random() * 0.2 + 0.1));

        State.city.gold -= CONFIG.ATTACK_COST;
        State.city.soldiers = State.city.soldiers - soldiersToSend + remaining;
        friend.soldiers = Math.max(0, friend.soldiers - defenderLosses);

        result = {
            ok: true, victory: false,
            msg: `💀 **شکست!**\n\n⚔️ سرباز ارسالی: ${faNum(soldiersToSend)}\n💀 تلفات شما: ${faNum(losses)}\n🛡️ تلفات دشمن: ${faNum(defenderLosses)} سرباز\n💪 دفاع شهر دشمن خیلی قوی بود (${faNum(defensePower)} vs ${faNum(attackPower)})`,
        };
    }

    saveGame();
    return result;
}

// ==========================================
// تجارت
// ==========================================
function tradeWithFriend(friendId, giveRes, giveAmt, takeRes, takeAmt) {
    const friend = State.friends.find(f => f.user_id === friendId);
    if (!friend) return { ok: false, msg: 'دوست پیدا نشد' };

    const valid = ['gold', 'wood', 'stone', 'food'];
    if (!valid.includes(giveRes) || !valid.includes(takeRes)) return { ok: false, msg: 'منبع نامعتبر' };
    if (giveAmt <= 0 || takeAmt <= 0) return { ok: false, msg: 'مقدار باید مثبت باشه' };
    if (State.city[giveRes] < giveAmt) return { ok: false, msg: `❌ ${giveRes} کافی نداری` };
    if (friend[takeRes] < takeAmt) return { ok: false, msg: `❌ دوستت ${takeRes} کافی نداره` };

    State.city[giveRes] -= giveAmt;
    State.city[takeRes] += takeAmt;
    friend[giveRes] = (friend[giveRes] || 0) + giveAmt;
    friend[takeRes] -= takeAmt;

    saveGame();
    const fa = { gold: 'طلا', wood: 'چوب', stone: 'سنگ', food: 'غذا' };
    return {
        ok: true,
        msg: `✅ **معامله موفق!**\n\nتو دادی: ${faNum(giveAmt)} ${fa[giveRes]}\nتو گرفتی: ${faNum(takeAmt)} ${fa[takeRes]}\nبا: ${friend.name}`,
    };
}

// ==========================================
// ذخیره/بازیابی بازی
// ==========================================
function saveGame() {
    Storage.save({
        city: State.city,
        buildings: State.buildings,
        friends: State.friends,
        lastSave: State.lastSave,
    });
}

function loadGame() {
    const data = Storage.load();
    if (data && data.city) {
        State.city = data.city;
        State.buildings = data.buildings || [];
        State.friends = data.friends || [];
        State.lastSave = data.lastSave || Date.now();
        return true;
    }
    return false;
}

function newGame(name) {
    State.city = {
        name: name || 'شهر من',
        ...CONFIG.INITIAL_RESOURCES,
        pop_cap: CONFIG.INITIAL_POP_CAP,
        soldiers: 0,
        city_level: 1,
    };
    State.buildings = [{ type: 'house', level: 1, count: 1 }];
    State.friends = [];
    State.lastSave = Date.now();
    saveGame();
}

// ==========================================
// رندر - نمایش شهر
// ==========================================
function showScreen(name) {
    $$('.screen').forEach(s => s.classList.add('hidden'));
    $(name + '-screen').classList.remove('hidden');
}

function openPanel(name) {
    closeAllPanels();
    $(`panel-${name}`).classList.remove('hidden');
}

function closeAllPanels() {
    $$('.panel').forEach(p => p.classList.add('hidden'));
}

function renderCity() {
    if (!State.city) return;
    const city = State.city;

    $('val-gold').textContent  = faNum(city.gold);
    $('val-wood').textContent  = faNum(city.wood);
    $('val-stone').textContent = faNum(city.stone);
    $('val-food').textContent  = faNum(city.food);
    $('city-level').textContent = `سطح ${faNum(city.city_level)}`;
    $('city-score').textContent = `${faNum(calculateScore())} امتیاز`;

    const popPct = (city.population / city.pop_cap) * 100;
    $('pop-bar-fill').style.width = popPct + '%';
    $('pop-text').textContent = `${faNum(city.population)}/${faNum(city.pop_cap)}`;

    renderCityGrid();
}

function renderCityGrid() {
    const grid = $('city-grid');
    grid.innerHTML = '';
    const totalBuildings = State.buildings.reduce((s, b) => s + b.count, 0);
    const gridSize = Math.max(12, Math.ceil(totalBuildings / 4) * 4 + 4);

    const expanded = [];
    State.buildings.forEach(b => {
        for (let i = 0; i < b.count; i++) expanded.push(b);
    });

    for (let i = 0; i < gridSize; i++) {
        const cell = document.createElement('div');
        cell.className = 'grid-cell';
        if (i < expanded.length) {
            const b = expanded[i];
            const art = BUILDING_ART[b.type] || { emoji: '❓' };
            cell.classList.add('has-building');
            cell.innerHTML = `
                <span class="building-emoji">${art.emoji}</span>
                ${b.level > 1 ? `<span class="building-level-badge">L${b.level}</span>` : ''}
            `;
            cell.onclick = () => showBuildingInfo(b);
        } else {
            cell.innerHTML = '<span style="opacity:0.3;font-size:18px;">➕</span>';
            cell.onclick = () => { openPanel('build'); renderBuildPanel(); };
        }
        grid.appendChild(cell);
    }
}

function showBuildingInfo(building) {
    const art = BUILDING_ART[building.type] || { emoji: building.type };
    const b = BUILDINGS[building.type];
    showToast(`${b ? b.name : art.emoji} - سطح ${building.level}`, '');
}

// ==========================================
// پنل ساخت
// ==========================================
function renderBuildPanel() {
    const list = $('build-list');
    list.innerHTML = '';
    const city = State.city;

    Object.entries(BUILDINGS).forEach(([type, b]) => {
        const card = document.createElement('div');
        card.className = 'build-card';
        const canAfford = Object.entries(b.cost).every(([res, amt]) => city[res] >= amt);
        const costHtml = Object.entries(b.cost).map(([res, amt]) => {
            const icon = { gold: '🪙', wood: '🪵', stone: '🪨', food: '🌾' }[res] || '';
            const cant = city[res] < amt ? 'cant-afford' : '';
            return `<span class="cost-item ${cant}">${icon}${faNum(amt)}</span>`;
        }).join('');

        card.innerHTML = `
            <div class="build-icon">${b.name.split(' ')[0]}</div>
            <div class="build-info">
                <div class="build-name">${b.name}</div>
                <div class="build-desc">${b.desc}</div>
                <div class="build-cost">${costHtml}</div>
            </div>
            <button class="pixel-btn pixel-btn-primary pixel-btn-small" ${canAfford ? '' : 'disabled'}>
                ${canAfford ? 'ساخت' : '❌'}
            </button>
        `;
        if (canAfford) {
            card.querySelector('button').onclick = () => doBuild(type);
        }
        list.appendChild(card);
    });
}

function doBuild(type) {
    const result = buildBuilding(type);
    showToast(result.msg, result.ok ? 'success' : 'error');
    if (result.ok) {
        flashResource();
        renderCity();
        renderBuildPanel();
    }
}

// ==========================================
// پنل ارتش
// ==========================================
function renderArmyPanel() {
    const content = $('army-content');
    const city = State.city;
    const barracks = State.buildings.find(b => b.type === 'barracks');
    const soldierCap = barracks ? 20 * barracks.level * barracks.count : 0;

    content.innerHTML = `
        <div class="army-stats">
            <div class="army-stat-row">
                <span class="army-stat-label">⚔️ سربازان فعلی</span>
                <span class="army-stat-value">${faNum(city.soldiers)}</span>
            </div>
            <div class="army-stat-row">
                <span class="army-stat-label">📊 ظرفیت پادگان</span>
                <span class="army-stat-value">${faNum(soldierCap)}</span>
            </div>
            <div class="army-stat-row">
                <span class="army-stat-label">🛡️ قدرت دفاعی</span>
                <span class="army-stat-value">${faNum(calculateDefense())}</span>
            </div>
            <div class="army-stat-row">
                <span class="army-stat-label">⚔️ قدرت حمله</span>
                <span class="army-stat-value">${faNum(city.soldiers * 10)}</span>
            </div>
        </div>
        ${barracks ? `
        <div class="train-section">
            <div class="section-title">🎓 آموزش سرباز جدید</div>
            <div style="font-size:11px;color:#aaa;margin-bottom:8px;">
                هزینه هر سرباز: 🪙۵۰ + 🌾۳۰
            </div>
            <div class="train-amount">
                ${[1, 5, 10, 20].map(n => `
                    <button data-amount="${n}" class="${n === State.selectedTrainAmount ? 'selected' : ''}">${faNum(n)}</button>
                `).join('')}
            </div>
            <button id="train-btn" class="pixel-btn pixel-btn-primary" style="width:100%;margin:8px 0 0 0;">
                🎓 آموزش ${faNum(State.selectedTrainAmount)} سرباز
            </button>
        </div>
        ` : `
        <div class="empty-state">
            <div class="empty-icon">⚔️</div>
            <div class="empty-text">برای آموزش سرباز اول باید سربازخانه بسازی!</div>
            <button class="pixel-btn pixel-btn-primary" onclick="closeAllPanels();openPanel('build');renderBuildPanel();">🏗️ ساخت سربازخانه</button>
        </div>
        `}
    `;

    $$('.train-amount button').forEach(btn => {
        btn.onclick = () => {
            State.selectedTrainAmount = parseInt(btn.dataset.amount);
            renderArmyPanel();
        };
    });
    const trainBtn = $('train-btn');
    if (trainBtn) trainBtn.onclick = () => doTrain(State.selectedTrainAmount);
}

function doTrain(count) {
    const result = trainSoldiers(count);
    showToast(result.msg, result.ok ? 'success' : 'error');
    if (result.ok) {
        flashResource('food');
        flashResource('gold');
        renderCity();
        renderArmyPanel();
    }
}

// ==========================================
// پنل دوستان
// ==========================================
function renderFriendsPanel() {
    const content = $('friends-content');
    growAllFriends();

    let html = `
        <div class="add-friend-form">
            <div class="section-title">➕ افزودن دوست جدید</div>
            <input type="number" id="friend-id-input" placeholder="آیدی عددی تلگرام (مثال: 123456789)" />
            <input type="text" id="friend-name-input" placeholder="نام شهر (اختیاری)" />
            <button class="pixel-btn pixel-btn-success" style="width:100%;margin:0;" id="add-friend-btn">
                ➕ افزودن
            </button>
        </div>
    `;

    if (State.friends.length === 0) {
        html += `
            <div class="empty-state">
                <div class="empty-icon">👥</div>
                <div class="empty-text">هنوز دوستی نداری!<br>با آیدی تلگرامش اضافه‌اش کن.</div>
            </div>
        `;
    } else {
        State.friends.forEach(f => {
            const score = getFriendScore(f);
            html += `
                <div class="friend-card">
                    <div class="friend-header">
                        <span class="friend-name">🏙️ ${f.name}</span>
                        <span class="friend-score">${faNum(score)} امتیاز</span>
                    </div>
                    <div class="friend-stats">
                        <span class="friend-stat">📊 سطح ${faNum(f.city_level)}</span>
                        <span class="friend-stat">👥 ${faNum(f.population)}</span>
                        <span class="friend-stat">⚔️ ${faNum(f.soldiers)}</span>
                    </div>
                    <div class="friend-actions">
                        <button class="pixel-btn pixel-btn-secondary pixel-btn-small" onclick="visitFriend(${f.user_id})">👁️ بازدید</button>
                        <button class="pixel-btn pixel-btn-danger pixel-btn-small" onclick="openAttackPanel(${f.user_id})">⚔️ حمله</button>
                        <button class="pixel-btn pixel-btn-success pixel-btn-small" onclick="openTradePanel(${f.user_id})">🤝 تجارت</button>
                        <button class="pixel-btn pixel-btn-secondary pixel-btn-small" onclick="removeFriend(${f.user_id})">🗑️ حذف</button>
                    </div>
                </div>
            `;
        });
    }

    content.innerHTML = html;
    $('add-friend-btn').onclick = async () => {
        const id = $('friend-id-input').value.trim();
        const name = $('friend-name-input').value.trim();
        if (!id) { showToast('❌ آیدی رو وارد کن', 'error'); return; }
        const result = addFriend(parseInt(id), name);
        showToast(result.msg, result.ok ? 'success' : 'error');
        if (result.ok) renderFriendsPanel();
    };
}

function visitFriend(friendId) {
    const friend = State.friends.find(f => f.user_id === friendId);
    if (!friend) { showToast('❌ دوست پیدا نشد', 'error'); return; }

    const score = getFriendScore(friend);
    $('visit-title').textContent = `👁️ ${friend.name}`;
    $('visit-content').innerHTML = `
        <div class="army-stats">
            <div class="army-stat-row"><span class="army-stat-label">📊 سطح شهر</span><span class="army-stat-value">${faNum(friend.city_level)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🏆 امتیاز</span><span class="army-stat-value">${faNum(score)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🪙 طلا</span><span class="army-stat-value">${faNum(friend.gold)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🪵 چوب</span><span class="army-stat-value">${faNum(friend.wood)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🪨 سنگ</span><span class="army-stat-value">${faNum(friend.stone)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🌾 غذا</span><span class="army-stat-value">${faNum(friend.food)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">👥 جمعیت</span><span class="army-stat-value">${faNum(friend.population)}/${faNum(friend.pop_cap)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">⚔️ سربازان</span><span class="army-stat-value">${faNum(friend.soldiers)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🛡️ دفاع کل</span><span class="army-stat-value">${faNum(friend.defense || friend.soldiers * 10)}</span></div>
        </div>
        <div class="friend-actions">
            <button class="pixel-btn pixel-btn-danger" onclick="closeAllPanels();openAttackPanel(${friend.user_id})">⚔️ حمله</button>
            <button class="pixel-btn pixel-btn-success" onclick="closeAllPanels();openTradePanel(${friend.user_id})">🤝 تجارت</button>
        </div>
    `;
    closeAllPanels();
    $('panel-visit').classList.remove('hidden');
}

function removeFriend(friendId) {
    showConfirm('حذف دوست', 'آیا مطمئنی؟', () => {
        removeFriend(friendId);
        showToast('✅ دوست حذف شد', 'success');
        renderFriendsPanel();
    });
}

// ==========================================
// پنل حمله
// ==========================================
function openAttackPanel(friendId) {
    const friend = State.friends.find(f => f.user_id === friendId);
    if (!friend) { showToast('❌ دوست پیدا نشد', 'error'); return; }

    $('attack-title').textContent = `⚔️ حمله به ${friend.name}`;
    const city = State.city;

    $('attack-content').innerHTML = `
        <div class="army-stats">
            <div class="army-stat-row"><span class="army-stat-label">⚔️ سربازان شما</span><span class="army-stat-value">${faNum(city.soldiers)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">🛡️ دفاع دشمن</span><span class="army-stat-value">${faNum(friend.defense || friend.soldiers * 10)}</span></div>
            <div class="army-stat-row"><span class="army-stat-label">💰 هزینه حمله</span><span class="army-stat-value">🪙${faNum(CONFIG.ATTACK_COST)}</span></div>
        </div>
        <div class="train-section">
            <div class="section-title">⚔️ تعداد سرباز ارسالی</div>
            <div class="train-amount" id="attack-amount">
                ${[1, 5, 10, 20, 50].map(n => {
                    const disabled = n > city.soldiers;
                    return `<button data-amount="${n}" ${disabled ? 'disabled style="opacity:0.4"' : ''}>${faNum(n)}</button>`;
                }).join('')}
                <button data-amount="${city.soldiers}">همه (${faNum(city.soldiers)})</button>
            </div>
            <div id="attack-info" style="text-align:center;font-size:12px;color:#aaa;padding:8px;"></div>
            <button id="attack-btn" class="pixel-btn pixel-btn-danger" style="width:100%;margin:8px 0 0 0;" disabled>⚔️ حمله!</button>
        </div>
    `;

    let selected = 0;
    $$('#attack-amount button').forEach(btn => {
        btn.onclick = () => {
            $$('#attack-amount button').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            selected = parseInt(btn.dataset.amount);
            $('attack-info').textContent = `قدرت حمله: ${faNum(selected * 10)} | هزینه: 🪙${faNum(CONFIG.ATTACK_COST)}`;
            $('attack-btn').disabled = false;
        };
    });

    $('attack-btn').onclick = () => doAttack(friendId, selected);
    closeAllPanels();
    $('panel-attack').classList.remove('hidden');
}

function doAttack(friendId, soldiers) {
    showBattleEffect();
    const result = attackCity(friendId, soldiers);
    showToast(result.msg, result.victory ? 'success' : 'error');
    if (result.ok) {
        renderCity();
        setTimeout(() => closeAllPanels(), 1500);
    }
}

function showBattleEffect() {
    const effect = document.createElement('div');
    effect.className = 'battle-effect';
    effect.textContent = '⚔️';
    document.body.appendChild(effect);
    setTimeout(() => effect.remove(), 800);
    document.body.classList.add('shake');
    setTimeout(() => document.body.classList.remove('shake'), 400);
}

// ==========================================
// پنل تجارت
// ==========================================
function openTradePanel(friendId) {
    const friend = State.friends.find(f => f.user_id === friendId);
    if (!friend) { showToast('❌ دوست پیدا نشد', 'error'); return; }

    State.selectedTradeFriend = friendId;
    $('trade-title').textContent = `🤝 تجارت با ${friend.name}`;
    const city = State.city;

    $('trade-content').innerHTML = `
        <div class="army-stats">
            <div class="army-stat-row"><span class="army-stat-label">شما می‌دهید</span><span class="army-stat-value" id="trade-give-preview">—</span></div>
            <div class="army-stat-row"><span class="army-stat-label">شما می‌گیرید</span><span class="army-stat-value" id="trade-take-preview">—</span></div>
        </div>
        <div class="trade-form">
            <div class="trade-row">
                <label>می‌دم:</label>
                <select id="give-res">
                    <option value="gold">🪙 طلا (${faNum(city.gold)})</option>
                    <option value="wood">🪵 چوب (${faNum(city.wood)})</option>
                    <option value="stone">🪨 سنگ (${faNum(city.stone)})</option>
                    <option value="food">🌾 غذا (${faNum(city.food)})</option>
                </select>
                <input type="number" id="give-amt" min="1" value="100" style="max-width:80px;" />
            </div>
            <div class="trade-arrow">⬇️</div>
            <div class="trade-row">
                <label>می‌گیرم:</label>
                <select id="take-res">
                    <option value="gold">🪙 طلا</option>
                    <option value="wood">🪵 چوب</option>
                    <option value="stone">🪨 سنگ</option>
                    <option value="food">🌾 غذا</option>
                </select>
                <input type="number" id="take-amt" min="1" value="50" style="max-width:80px;" />
            </div>
            <button id="trade-btn" class="pixel-btn pixel-btn-success" style="width:100%;margin:10px 0 0 0;">🤝 انجام معامله</button>
        </div>
    `;

    const updatePreview = () => {
        const gr = $('give-res').value, ga = $('give-amt').value || 0;
        const tr = $('take-res').value, ta = $('take-amt').value || 0;
        const icons = { gold: '🪙', wood: '🪵', stone: '🪨', food: '🌾' };
        $('trade-give-preview').textContent = `${icons[gr]} ${faNum(ga)}`;
        $('trade-take-preview').textContent = `${icons[tr]} ${faNum(ta)}`;
    };
    ['give-res','give-amt','take-res','take-amt'].forEach(id => $(id).oninput = updatePreview);
    updatePreview();
    $('trade-btn').onclick = () => doTrade();

    closeAllPanels();
    $('panel-trade').classList.remove('hidden');
}

function doTrade() {
    const friendId = State.selectedTradeFriend;
    const giveRes = $('give-res').value;
    const giveAmt = parseInt($('give-amt').value);
    const takeRes = $('take-res').value;
    const takeAmt = parseInt($('take-amt').value);

    const result = tradeWithFriend(friendId, giveRes, giveAmt, takeRes, takeAmt);
    showToast(result.msg, result.ok ? 'success' : 'error');
    if (result.ok) {
        flashResource(giveRes);
        flashResource(takeRes);
        renderCity();
        closeAllPanels();
    }
}

// ==========================================
// لیدربورد
// ==========================================
function renderLeaderboardPanel() {
    const content = $('leaderboard-content');
    const cities = [
        { name: State.city.name, city_level: State.city.city_level, population: State.city.population, soldiers: State.city.soldiers, score: calculateScore(), is_me: true },
        ...State.friends.map(f => ({
            name: f.name, city_level: f.city_level, population: f.population,
            soldiers: f.soldiers, score: getFriendScore(f), is_me: false,
        })),
    ];
    cities.sort((a, b) => b.score - a.score);

    if (cities.length === 0) {
        content.innerHTML = `<div class="empty-state"><div class="empty-icon">🏆</div><div class="empty-text">هنوز شهری ثبت نشده!</div></div>`;
        return;
    }

    const medals = ['🥇', '🥈', '🥉'];
    let html = '';
    cities.forEach((c, i) => {
        const rank = i < 3 ? medals[i] : `${faNum(i + 1)}.`;
        const me = c.is_me ? ' me' : '';
        html += `
            <div class="leaderboard-item${me}">
                <div class="leaderboard-rank">${rank}</div>
                <div class="leaderboard-info">
                    <div class="leaderboard-name">${c.name} ${c.is_me ? '(شما)' : ''}</div>
                    <div class="leaderboard-stats">سطح ${faNum(c.city_level)} • امتیاز ${faNum(c.score)} • 👥 ${faNum(c.population)}</div>
                </div>
            </div>
        `;
    });
    content.innerHTML = html;
}

// ==========================================
// افکت‌ها
// ==========================================
function flashResource(resource) {
    if (resource) {
        const el = $('res-' + resource);
        if (el) {
            el.classList.add('flash');
            setTimeout(() => el.classList.remove('flash'), 400);
        }
    } else {
        ['gold', 'wood', 'stone', 'food'].forEach(r => {
            const el = $('res-' + r);
            if (el) { el.classList.add('flash'); setTimeout(() => el.classList.remove('flash'), 400); }
        });
    }
}

// ==========================================
// شروع بازی
// ==========================================
function startGame() {
    if (!State.city) newGame('شهر من');
    collectResources();
    growAllFriends();
    renderCity();
    showScreen('game');
    showToast('🎉 خوش اومدی!', 'success');

    if (State.autoTimer) clearInterval(State.autoTimer);
    State.autoTimer = setInterval(() => {
        collectResources();
        growAllFriends();
        renderCity();
    }, 30000);
}

// ==========================================
// راه‌اندازی اولیه
// ==========================================
function init() {
    setTimeout(() => $('loader').classList.add('hidden'), 1500);

    $('start-game-btn').onclick = () => {
        newGame();
        startGame();
    };
    $('continue-game-btn').onclick = startGame;

    $$('.nav-btn').forEach(btn => {
        btn.onclick = () => {
            const screen = btn.dataset.screen;
            $$('.nav-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (screen === 'city') { closeAllPanels(); collectResources(); renderCity(); }
            else if (screen === 'build') { openPanel('build'); renderBuildPanel(); }
            else if (screen === 'army') { openPanel('army'); renderArmyPanel(); }
            else if (screen === 'friends') { openPanel('friends'); renderFriendsPanel(); }
            else if (screen === 'leaderboard') { openPanel('leaderboard'); renderLeaderboardPanel(); }
        };
    });

    $$('[data-close-panel]').forEach(btn => {
        btn.onclick = () => {
            closeAllPanels();
            $$('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelector('.nav-btn[data-screen="city"]').classList.add('active');
        };
    });

    // اگه بازی ذخیره‌شده هست، دکمه‌ی ادامه رو نشون بده
    if (loadGame()) {
        $('continue-game-btn').classList.remove('hidden');
        $('start-game-btn').textContent = '🔄 شروع از نو';
    }

    setTimeout(() => showScreen('welcome'), 1500);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
