const REFRESH_INTERVAL = 60_000;
const MAX_HISTORY_ROWS = 12;
const MAX_NEWS_ITEMS = 12;

const currencyFormatterCache = new Map();
const signedPercentFormatter = new Intl.NumberFormat('ko-KR', {
  style: 'percent',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'always',
});
const numberFormatter = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 0,
});
const quantityFormatter = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 6,
});
const dateTimeFormatter = new Intl.DateTimeFormat('ko-KR', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

function currencyKey(currency, value) {
  if (currency !== 'KRW') {
    return value >= 1 ? `${currency}|unit` : `${currency}|fraction`;
  }
  if (value >= 100_000) return 'KRW|large';
  if (value >= 1) return 'KRW|default';
  return 'KRW|small';
}

function currencyDigits(key) {
  switch (key) {
    case 'KRW|large':
      return 0;
    case 'KRW|default':
      return 0;
    case 'KRW|small':
      return 4;
    default:
      return key.endsWith('fraction') ? 4 : 2;
  }
}

function formatCurrency(rawValue, currency = 'KRW') {
  const value = Number(rawValue);
  if (!Number.isFinite(value)) {
    return '-';
  }
  const key = currencyKey(currency, value);
  if (!currencyFormatterCache.has(key)) {
    currencyFormatterCache.set(
      key,
      new Intl.NumberFormat('ko-KR', {
        style: 'currency',
        currency,
        maximumFractionDigits: currencyDigits(key),
      }),
    );
  }
  try {
    return currencyFormatterCache.get(key).format(value);
  } catch (error) {
    return `${value.toLocaleString('ko-KR', { maximumFractionDigits: 2 })} ${currency}`;
  }
}

function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return '-';
  }
  return signedPercentFormatter.format(numeric / 100);
}

function formatQuantity(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return '-';
  }
  return quantityFormatter.format(numeric);
}

function formatNumber(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return '-';
  }
  return numberFormatter.format(numeric);
}

function formatDateTime(value) {
  if (!value) {
    return null;
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return dateTimeFormatter.format(date);
}

function translateAction(action) {
  switch (action) {
    case 'buy':
      return '매수';
    case 'sell':
      return '매도';
    case 'hold':
      return '관망';
    default:
      return action ?? '-';
  }
}

function translateSentiment(label) {
  switch (label) {
    case 'positive':
      return '긍정';
    case 'negative':
      return '부정';
    case 'neutral':
    default:
      return '중립';
  }
}

function setStatus({ ok, lastUpdated, error }) {
  const indicator = document.getElementById('status-indicator');
  const statusText = document.getElementById('status-text');
  if (!indicator || !statusText) return;

  indicator.classList.remove('online', 'offline');
  if (ok) {
    indicator.classList.add('online');
    const formatted = lastUpdated ? formatDateTime(lastUpdated) : null;
    statusText.textContent = formatted ? `마지막 업데이트 ${formatted}` : '데이터 동기화 완료';
  } else {
    indicator.classList.add('offline');
    statusText.textContent = error ? `데이터 로드 실패: ${error}` : '데이터 연결 실패';
  }
}

function updateSummary(state) {
  const portfolio = state.portfolio ?? {};
  const baseCurrency = portfolio.baseCurrency ?? 'KRW';
  const portfolioValue = document.getElementById('portfolio-value');
  const cashBalance = document.getElementById('cash-balance');
  const positionsCount = document.getElementById('positions-count');
  const portfolioBase = document.getElementById('portfolio-base');
  const sentimentScore = document.getElementById('sentiment-score');
  const positive = document.getElementById('sentiment-positive');
  const neutral = document.getElementById('sentiment-neutral');
  const negative = document.getElementById('sentiment-negative');

  if (portfolioValue) {
    portfolioValue.textContent = formatCurrency(portfolio.totalValue ?? 0, baseCurrency);
  }
  if (cashBalance) {
    cashBalance.textContent = formatCurrency(portfolio.cash ?? 0, baseCurrency);
  }
  if (positionsCount) {
    positionsCount.textContent = formatNumber(portfolio.positionsCount ?? 0);
  }
  if (portfolioBase) {
    portfolioBase.textContent = `기준 통화: ${baseCurrency}`;
  }

  const sentiment = state.sentiment ?? {};
  const summary = sentiment.summary ?? {};
  const avgScore = Number(sentiment.averageScore ?? 0);
  if (positive) positive.textContent = `긍정 ${summary.positive ?? 0}`;
  if (neutral) neutral.textContent = `중립 ${summary.neutral ?? 0}`;
  if (negative) negative.textContent = `부정 ${summary.negative ?? 0}`;
  if (sentimentScore) {
    const sign = avgScore > 0 ? '+' : '';
    sentimentScore.textContent = `평균 점수 ${sign}${avgScore.toFixed(2)}`;
  }
}

function renderMarket(market) {
  const tbody = document.getElementById('market-body');
  const timestampEl = document.getElementById('market-timestamp');
  if (!tbody) return;

  tbody.innerHTML = '';
  if (!market || !market.items || market.items.length === 0) {
    tbody.innerHTML = '<tr><td class="placeholder" colspan="6">시장 데이터가 아직 수집되지 않았습니다.</td></tr>';
    if (timestampEl) {
      timestampEl.textContent = '업데이트 대기 중';
    }
    return;
  }

  const sorted = [...market.items].sort((a, b) => a.symbol.localeCompare(b.symbol));
  for (const item of sorted) {
    const row = document.createElement('tr');

    const symbolCell = document.createElement('td');
    symbolCell.textContent = item.symbol;
    row.appendChild(symbolCell);

    const priceCell = document.createElement('td');
    priceCell.textContent = formatCurrency(item.price, item.baseCurrency ?? 'KRW');
    row.appendChild(priceCell);

    const changeCell = document.createElement('td');
    changeCell.textContent = formatPercent(item.change24h);
    if (item.change24h > 0) changeCell.classList.add('positive-change');
    else if (item.change24h < 0) changeCell.classList.add('negative-change');
    row.appendChild(changeCell);

    const highCell = document.createElement('td');
    highCell.textContent = Number.isFinite(item.high24h) ? formatCurrency(item.high24h, item.baseCurrency ?? 'KRW') : '-';
    row.appendChild(highCell);

    const lowCell = document.createElement('td');
    lowCell.textContent = Number.isFinite(item.low24h) ? formatCurrency(item.low24h, item.baseCurrency ?? 'KRW') : '-';
    row.appendChild(lowCell);

    const volumeCell = document.createElement('td');
    volumeCell.textContent = formatNumber(item.volume24h ?? 0);
    row.appendChild(volumeCell);

    tbody.appendChild(row);
  }

  if (timestampEl) {
    const formatted = formatDateTime(market.timestamp);
    timestampEl.textContent = formatted ? `시장 기준 ${formatted}` : '업데이트 시간 정보 없음';
  }
}

function renderPositions(portfolio) {
  const tbody = document.getElementById('positions-body');
  if (!tbody) return;

  tbody.innerHTML = '';
  const positions = (portfolio?.positions ?? []).filter((item) => Number(item.quantity) > 0);
  if (positions.length === 0) {
    tbody.innerHTML = '<tr><td class="placeholder" colspan="5">보유 중인 포지션이 없습니다.</td></tr>';
    return;
  }

  const sorted = [...positions].sort((a, b) => (b.currentValue ?? 0) - (a.currentValue ?? 0));
  const baseCurrency = portfolio?.baseCurrency ?? 'KRW';

  for (const position of sorted) {
    const row = document.createElement('tr');

    const symbolCell = document.createElement('td');
    symbolCell.textContent = position.symbol;
    row.appendChild(symbolCell);

    const qtyCell = document.createElement('td');
    qtyCell.textContent = formatQuantity(position.quantity ?? 0);
    row.appendChild(qtyCell);

    const avgCell = document.createElement('td');
    avgCell.textContent = formatCurrency(position.averagePrice ?? 0, baseCurrency);
    row.appendChild(avgCell);

    const priceCell = document.createElement('td');
    priceCell.textContent = Number.isFinite(position.currentPrice)
      ? formatCurrency(position.currentPrice, baseCurrency)
      : '-';
    row.appendChild(priceCell);

    const valueCell = document.createElement('td');
    valueCell.textContent = Number.isFinite(position.currentValue)
      ? formatCurrency(position.currentValue, baseCurrency)
      : '-';
    row.appendChild(valueCell);

    tbody.appendChild(row);
  }
}

function renderHistory(portfolio, baseCurrency = 'KRW') {
  const tbody = document.getElementById('history-body');
  if (!tbody) return;

  tbody.innerHTML = '';
  const history = portfolio?.history ?? [];
  if (history.length === 0) {
    tbody.innerHTML = '<tr><td class="placeholder" colspan="6">최근 체결 내역이 없습니다.</td></tr>';
    return;
  }

  for (const record of history.slice(0, MAX_HISTORY_ROWS)) {
    const row = document.createElement('tr');

    const timeCell = document.createElement('td');
    timeCell.textContent = formatDateTime(record.timestamp) ?? '-';
    row.appendChild(timeCell);

    const symbolCell = document.createElement('td');
    symbolCell.textContent = record.symbol;
    row.appendChild(symbolCell);

    const actionCell = document.createElement('td');
    actionCell.textContent = translateAction(record.action);
    row.appendChild(actionCell);

    const qtyCell = document.createElement('td');
    qtyCell.textContent = formatQuantity(record.quantity ?? 0);
    row.appendChild(qtyCell);

    const priceCell = document.createElement('td');
    priceCell.textContent = formatCurrency(record.price ?? 0, baseCurrency);
    row.appendChild(priceCell);

    const reasonCell = document.createElement('td');
    reasonCell.textContent = record.reasoning ?? '-';
    row.appendChild(reasonCell);

    tbody.appendChild(row);
  }
}

function renderDecisions(state) {
  const list = document.getElementById('decision-list');
  if (!list) return;

  list.innerHTML = '';
  const decisions = state.decisions ?? [];
  const countEl = document.getElementById('decision-count');
  const summary = state.decisionSummary ?? {};
  const summaryParts = [];
  if ((summary.buy ?? 0) > 0) summaryParts.push(`매수 ${summary.buy}`);
  if ((summary.sell ?? 0) > 0) summaryParts.push(`매도 ${summary.sell}`);
  if ((summary.hold ?? 0) > 0) summaryParts.push(`관망 ${summary.hold}`);
  if (countEl) {
    countEl.textContent = `${decisions.length}건${summaryParts.length ? ` · ${summaryParts.join(' / ')}` : ''}`;
  }

  if (decisions.length === 0) {
    list.innerHTML = '<li class="placeholder">현재 대기 중인 의사결정이 없습니다.</li>';
    return;
  }

  const baseCurrency = state.portfolio?.baseCurrency ?? 'KRW';
  for (const decision of decisions) {
    const item = document.createElement('li');
    item.className = 'decision-item';

    const header = document.createElement('div');
    header.className = 'meta';
    header.innerHTML = `<strong>${decision.symbol}</strong><span>${formatDateTime(decision.createdAt) ?? ''}</span>`;

    const badge = document.createElement('span');
    badge.className = `badge ${decision.action}`;
    badge.textContent = translateAction(decision.action);

    const price = document.createElement('div');
    price.className = 'decision-price';
    price.textContent = `가격 ${formatCurrency(decision.price ?? 0, baseCurrency)}`;

    const confidence = document.createElement('div');
    confidence.className = 'decision-confidence';
    const confidencePct = Math.round((decision.confidence ?? 0) * 100);
    confidence.textContent = `신뢰도 ${confidencePct}%`;

    const reasoning = document.createElement('p');
    reasoning.textContent = decision.reasoning ?? '-';

    item.appendChild(header);
    item.appendChild(badge);
    item.appendChild(price);
    item.appendChild(confidence);
    item.appendChild(reasoning);
    list.appendChild(item);
  }
}

function renderNews(news) {
  const container = document.getElementById('news-list');
  if (!container) return;

  container.innerHTML = '';
  const countEl = document.getElementById('news-count');
  if (countEl) {
    countEl.textContent = `${news?.length ?? 0}건`;
  }

  if (!news || news.length === 0) {
    container.innerHTML = '<p class="placeholder">관련 뉴스가 수집되면 이곳에 표시됩니다.</p>';
    return;
  }

  for (const article of news.slice(0, MAX_NEWS_ITEMS)) {
    const card = document.createElement('article');
    card.className = 'news-card';

    const title = document.createElement('h3');
    const link = document.createElement('a');
    link.href = article.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = article.title ?? '제목 없음';
    title.appendChild(link);

    const meta = document.createElement('div');
    meta.className = 'meta';
    const published = formatDateTime(article.publishedAt) ?? '시간 정보 없음';
    meta.textContent = `${article.source ?? '알 수 없음'} · ${published}`;

    const summary = document.createElement('p');
    summary.textContent = article.summary ?? '요약 정보가 제공되지 않았습니다.';

    card.appendChild(title);
    card.appendChild(meta);
    card.appendChild(summary);

    if (article.sentiment) {
      const chip = document.createElement('span');
      chip.className = `sentiment-chip ${article.sentiment.label}`;
      const label = translateSentiment(article.sentiment.label);
      chip.textContent = `${label} (${article.sentiment.score.toFixed(2)})`;
      card.appendChild(chip);

      if (article.sentiment.reasoning) {
        const reasoning = document.createElement('p');
        reasoning.className = 'meta';
        reasoning.textContent = article.sentiment.reasoning;
        card.appendChild(reasoning);
      }
    }

    if (article.symbols && article.symbols.length > 0) {
      const symbols = document.createElement('div');
      symbols.className = 'symbol-tags';
      for (const symbol of article.symbols) {
        const tag = document.createElement('span');
        tag.className = 'symbol-tag';
        tag.textContent = symbol;
        symbols.appendChild(tag);
      }
      card.appendChild(symbols);
    }

    container.appendChild(card);
  }
}

function renderDashboard(data) {
  updateSummary(data);
  renderMarket(data.market);
  renderPositions(data.portfolio);
  renderHistory(data.portfolio, data.portfolio?.baseCurrency ?? 'KRW');
  renderDecisions(data);
  renderNews(data.news);
}

async function fetchState() {
  try {
    const response = await fetch('/api/state', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    renderDashboard(data);
    setStatus({ ok: true, lastUpdated: data.lastUpdated ?? data.market?.timestamp ?? null });
  } catch (error) {
    console.error('상태 조회 실패', error);
    setStatus({ ok: false, error: error.message });
  }
}


document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    fetchState();
  }
});

fetchState();
setInterval(() => {
  if (!document.hidden) {
    fetchState();
  }
}, REFRESH_INTERVAL);
