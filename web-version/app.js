(function () {
  'use strict';

  const E = window.GomokuEngine;
  if (!E) {
    throw new Error('GomokuEngine 未加载');
  }

  const SIZE = E.SIZE;
  const CELL_PERCENT = 100 / SIZE;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const STONE_LABEL = {
    [E.BLACK]: '黑棋',
    [E.WHITE]: '白棋',
  };

  const RPS = {
    rock: { label: '石头', icon: '✊', beats: 'scissors' },
    scissors: { label: '剪刀', icon: '✌️', beats: 'paper' },
    paper: { label: '布', icon: '✋', beats: 'rock' },
  };
  const RPS_KEYS = Object.keys(RPS);

  const els = {
    app: document.getElementById('app'),
    board: document.getElementById('board'),
    cells: document.getElementById('cells'),
    gridLines: document.getElementById('gridLines'),
    starPoints: document.getElementById('starPoints'),
    stonesLayer: document.getElementById('stonesLayer'),
    winLayer: document.getElementById('winLayer'),
    winLine: document.getElementById('winLine'),
    boardResult: document.getElementById('boardResult'),
    resultCard: document.getElementById('resultCard'),
    resultKicker: document.getElementById('resultKicker'),
    resultTitle: document.getElementById('resultTitle'),
    resultText: document.getElementById('resultText'),
    rematchBtn: document.getElementById('rematchBtn'),
    reviewBtn: document.getElementById('reviewBtn'),
    statusStone: document.getElementById('statusStone'),
    statusText: document.getElementById('statusText'),
    thinkingDots: document.getElementById('thinkingDots'),
    difficultyPill: document.getElementById('difficultyPill'),
    humanCard: document.getElementById('humanCard'),
    aiCard: document.getElementById('aiCard'),
    humanColor: document.getElementById('humanColor'),
    aiColor: document.getElementById('aiColor'),
    humanTurnPill: document.getElementById('humanTurnPill'),
    aiTurnPill: document.getElementById('aiTurnPill'),
    moveCount: document.getElementById('moveCount'),
    matchState: document.getElementById('matchState'),
    undoBtn: document.getElementById('undoBtn'),
    restartBtn: document.getElementById('restartBtn'),
    setupModal: document.getElementById('setupModal'),
    setupCloseBtn: document.getElementById('setupCloseBtn'),
    difficultyList: document.getElementById('difficultyList'),
    rpsPanel: document.getElementById('rpsPanel'),
    rpsHands: document.getElementById('rpsHands'),
    playerHand: document.getElementById('playerHand'),
    aiHand: document.getElementById('aiHand'),
    rpsHint: document.getElementById('rpsHint'),
    rpsButtons: document.getElementById('rpsButtons'),
    startGameBtn: document.getElementById('startGameBtn'),
    rulesBtn: document.getElementById('rulesBtn'),
    rulesModal: document.getElementById('rulesModal'),
    rulesCloseBtn: document.getElementById('rulesCloseBtn'),
    rulesOkBtn: document.getElementById('rulesOkBtn'),
    toast: document.getElementById('toast'),
  };

  const cellEls = [];
  const stoneEls = new Map();

  const state = {
    board: E.createBoard(),
    history: [],
    selectedDifficulty: 'medium',
    gameDifficulty: 'medium',
    playerColor: E.BLACK,
    aiColor: E.WHITE,
    current: E.BLACK,
    phase: 'idle',
    winner: 0,
    winLine: null,
    lastMove: -1,
    gameStarted: false,
    pendingFirst: null,
    setupResumable: false,
    resultDismissed: false,
    resultDelay: false,
    gameToken: 0,
    aiTimer: null,
    resultTimer: null,
    rpsToken: 0,
    rpsLock: false,
    toastTimer: null,
    focusMove: 6 * SIZE + 6,
  };

  function createSvgElement(name, attributes) {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes || {}).forEach(([key, value]) => {
      element.setAttribute(key, String(value));
    });
    return element;
  }

  function drawBoardLines() {
    const pad = 100 / (SIZE * 2);
    const end = 100 - pad;

    for (let i = 0; i < SIZE; i += 1) {
      const position = pad + i * CELL_PERCENT;
      const edge = i === 0 || i === SIZE - 1;

      const vertical = createSvgElement('line', {
        x1: position,
        y1: pad,
        x2: position,
        y2: end,
        'vector-effect': 'non-scaling-stroke',
      });
      const horizontal = createSvgElement('line', {
        x1: pad,
        y1: position,
        x2: end,
        y2: position,
        'vector-effect': 'non-scaling-stroke',
      });

      if (edge) {
        vertical.setAttribute('class', 'is-edge');
        horizontal.setAttribute('class', 'is-edge');
      }

      els.gridLines.append(vertical, horizontal);
    }

    [[3, 3], [3, 10], [10, 3], [10, 10]].forEach(([row, col]) => {
      const dot = createSvgElement('circle', {
        cx: (col + 0.5) * CELL_PERCENT,
        cy: (row + 0.5) * CELL_PERCENT,
        r: 0.48,
      });
      els.starPoints.appendChild(dot);
    });
  }

  function buildCells() {
    els.cells.innerHTML = '';
    cellEls.length = 0;

    for (let row = 0; row < SIZE; row += 1) {
      for (let col = 0; col < SIZE; col += 1) {
        const move = row * SIZE + col;
        const cell = document.createElement('button');
        cell.type = 'button';
        cell.className = 'cell';
        cell.dataset.move = String(move);
        cell.dataset.row = String(row);
        cell.dataset.col = String(col);
        cell.setAttribute('role', 'gridcell');
        cell.setAttribute('aria-rowindex', String(row + 1));
        cell.setAttribute('aria-colindex', String(col + 1));
        cell.setAttribute('aria-label', `第 ${row + 1} 行，第 ${col + 1} 列`);
        cell.setAttribute('aria-disabled', 'true');
        cell.tabIndex = move === state.focusMove ? 0 : -1;
        els.cells.appendChild(cell);
        cellEls.push(cell);
      }
    }
  }

  function updateModalLock() {
    const open = !els.setupModal.hidden || !els.rulesModal.hidden;
    document.body.classList.toggle('modal-open', open);
    if (open) els.app.setAttribute('inert', '');
    else els.app.removeAttribute('inert');
  }

  function showModal(layer) {
    layer.hidden = false;
    updateModalLock();
  }

  function hideModal(layer) {
    layer.hidden = true;
    updateModalLock();
  }

  function selectDifficulty(level) {
    if (!E.DIFFICULTIES[level]) return;
    state.selectedDifficulty = level;
    syncDifficultyUI();
  }

  function syncDifficultyUI() {
    els.difficultyList.querySelectorAll('.difficulty-option').forEach((button) => {
      const active = button.dataset.level === state.selectedDifficulty;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-checked', active ? 'true' : 'false');
    });
    els.difficultyPill.textContent =
      E.DIFFICULTIES[state.gameStarted ? state.gameDifficulty : state.selectedDifficulty].label;
  }

  function resetRPS() {
    state.rpsToken += 1;
    state.rpsLock = false;
    state.pendingFirst = null;

    els.playerHand.textContent = '?';
    els.aiHand.textContent = '?';
    els.playerHand.classList.remove('pop');
    els.aiHand.classList.remove('pop');
    els.rpsHands.classList.remove('is-shaking');
    els.rpsPanel.className = 'rps-panel';
    els.rpsHint.className = 'rps-hint';
    els.rpsHint.textContent = '选一个手势 · 赢家执黑先行';
    els.startGameBtn.hidden = true;
    els.startGameBtn.textContent = '开始对局';

    els.rpsButtons.querySelectorAll('button').forEach((button) => {
      button.disabled = false;
    });
  }

  function openSetup() {
    hideToast();
    state.setupResumable = state.gameStarted && state.phase !== 'ai';
    els.setupCloseBtn.hidden = !state.setupResumable;
    resetRPS();
    syncDifficultyUI();
    showModal(els.setupModal);
    const modalBody = els.setupModal.querySelector('.modal');
    if (modalBody) modalBody.scrollTop = 0;
  }

  function closeSetup() {
    if (!state.setupResumable) return;
    hideModal(els.setupModal);
    state.setupResumable = false;
    els.setupCloseBtn.hidden = true;
    window.setTimeout(() => els.restartBtn.focus({ preventScroll: true }), 30);
  }

  function openRules() {
    hideToast();
    showModal(els.rulesModal);
    window.setTimeout(() => els.rulesCloseBtn.focus({ preventScroll: true }), 40);
  }

  function closeRules() {
    hideModal(els.rulesModal);
    els.rulesBtn.focus({ preventScroll: true });
  }

  function popHand(element) {
    element.classList.remove('pop');
    void element.offsetWidth;
    element.classList.add('pop');
  }

  function judgeRPS(playerGesture, aiGesture) {
    if (playerGesture === aiGesture) return 0;
    return RPS[playerGesture].beats === aiGesture ? 1 : -1;
  }

  function playRPS(playerGesture) {
    if (state.rpsLock || state.pendingFirst !== null || els.setupModal.hidden) return;
    if (!RPS[playerGesture]) return;

    state.rpsLock = true;
    const token = state.rpsToken;
    const buttons = els.rpsButtons.querySelectorAll('button');
    buttons.forEach((button) => {
      button.disabled = true;
    });

    els.rpsPanel.classList.remove('is-decided', 'is-tie', 'is-win', 'is-lose');
    els.rpsHint.className = 'rps-hint';
    els.rpsHint.textContent = '出拳中…';
    els.playerHand.textContent = RPS[playerGesture].icon;
    els.aiHand.textContent = '?';
    popHand(els.playerHand);
    els.rpsHands.classList.remove('is-shaking');
    void els.rpsHands.offsetWidth;
    els.rpsHands.classList.add('is-shaking');

    window.setTimeout(() => {
      if (token !== state.rpsToken || els.setupModal.hidden) return;

      const aiGesture = RPS_KEYS[Math.floor(Math.random() * RPS_KEYS.length)];
      const outcome = judgeRPS(playerGesture, aiGesture);
      els.aiHand.textContent = RPS[aiGesture].icon;
      popHand(els.aiHand);
      els.rpsHands.classList.remove('is-shaking');

      if (outcome === 0) {
        state.rpsLock = false;
        buttons.forEach((button) => {
          button.disabled = false;
        });
        els.rpsPanel.classList.add('is-tie');
        els.rpsHint.className = 'rps-hint is-tie';
        els.rpsHint.textContent =
          `平局！你们都出了${RPS[playerGesture].label}，再猜一次`;
        return;
      }

      state.pendingFirst = outcome > 0;
      els.rpsPanel.classList.add('is-decided', outcome > 0 ? 'is-win' : 'is-lose');
      els.rpsHint.className = `rps-hint ${outcome > 0 ? 'is-win' : 'is-lose'}`;
      els.rpsHint.textContent = outcome > 0
        ? `你出${RPS[playerGesture].label}，弈者出${RPS[aiGesture].label} —— 你赢了，执黑先行`
        : `你出${RPS[playerGesture].label}，弈者出${RPS[aiGesture].label} —— 弈者执黑先行`;
      els.startGameBtn.textContent = outcome > 0 ? '我执黑 · 开始对局' : '弈者执黑 · 开始对局';
      els.startGameBtn.hidden = false;
    }, 520);
  }

  function hideResultOverlay() {
    state.resultDismissed = true;
    els.boardResult.hidden = true;
  }

  function showResult(winner, reason) {
    let kicker = 'DRAW';
    let title = '平局';
    let text = '棋盘已满，势均力敌。';
    let tone = 'is-draw';

    if (winner !== 0 && winner === state.playerColor) {
      kicker = 'VICTORY';
      title = '你赢了';
      text = reason === 'noLegal'
        ? '黑棋已无合法落点，本局结束。'
        : state.winLine && state.winLine.length > 5
          ? '长连取胜，漂亮的一局。'
          : '五子连珠，漂亮的一局。';
      tone = 'is-win';
    } else if (winner !== 0 && winner === state.aiColor) {
      kicker = 'DEFEAT';
      title = '弈者获胜';
      text = reason === 'noLegal'
        ? '黑棋已无合法落点，本局结束。'
        : state.winLine && state.winLine.length > 5
          ? '弈者以长连取胜，再来一局？'
          : state.gameDifficulty === 'hard'
            ? '困难模式的弈者算到了后面几步，再来一局？'
            : '这一局棋差一着，调整思路再来。';
      tone = 'is-loss';
    }

    els.resultKicker.textContent = kicker;
    els.resultTitle.textContent = title;
    els.resultText.textContent = text;
    els.resultCard.classList.remove('is-win', 'is-loss', 'is-draw');
    els.resultCard.classList.add(tone);

    state.resultDismissed = false;
    state.resultDelay = true;
    window.clearTimeout(state.resultTimer);
    state.resultTimer = window.setTimeout(() => {
      if (state.phase !== 'over' || state.resultDismissed) return;
      state.resultDelay = false;
      updateUI();
    }, state.winLine ? 620 : 280);
  }

  function clearResultTimer() {
    window.clearTimeout(state.resultTimer);
    state.resultTimer = null;
    state.resultDelay = false;
  }

  function addStoneElement(move, player, animate) {
    const row = E.rowOf(move);
    const col = E.colOf(move);
    const stone = document.createElement('span');
    stone.className = `stone ${player === E.BLACK ? 'black' : 'white'}${animate ? ' drop' : ''}`;
    stone.style.left = `${(col + 0.5) * CELL_PERCENT}%`;
    stone.style.top = `${(row + 0.5) * CELL_PERCENT}%`;
    stone.dataset.move = String(move);
    els.stonesLayer.appendChild(stone);
    stoneEls.set(move, stone);
    return stone;
  }

  function rebuildStones() {
    els.stonesLayer.replaceChildren();
    stoneEls.clear();
    for (const entry of state.history) {
      addStoneElement(entry.move, entry.player, false);
    }
    syncLastStone();
  }

  function clearStones() {
    els.stonesLayer.replaceChildren();
    stoneEls.clear();
  }

  function syncLastStone() {
    stoneEls.forEach((stone, move) => {
      stone.classList.toggle('is-last', move === state.lastMove);
    });
  }

  function clearWinMarks() {
    stoneEls.forEach((stone) => stone.classList.remove('is-win'));
    els.winLine.classList.remove('show');
    els.winLine.setAttribute('x1', '0');
    els.winLine.setAttribute('y1', '0');
    els.winLine.setAttribute('x2', '0');
    els.winLine.setAttribute('y2', '0');
  }

  function markWinningStones(line) {
    for (const move of line) {
      const stone = stoneEls.get(move);
      if (stone) stone.classList.add('is-win');
    }
  }

  function drawWinLine(line) {
    const first = line[0];
    const last = line[line.length - 1];
    const x1 = (E.colOf(first) + 0.5) * CELL_PERCENT;
    const y1 = (E.rowOf(first) + 0.5) * CELL_PERCENT;
    const x2 = (E.colOf(last) + 0.5) * CELL_PERCENT;
    const y2 = (E.rowOf(last) + 0.5) * CELL_PERCENT;

    els.winLine.setAttribute('x1', String(x1));
    els.winLine.setAttribute('y1', String(y1));
    els.winLine.setAttribute('x2', String(x2));
    els.winLine.setAttribute('y2', String(y2));
    els.winLine.classList.remove('show');
    void els.winLine.getBoundingClientRect();
    els.winLine.classList.add('show');
  }

  function syncCells() {
    const canPlay = state.gameStarted && state.phase === 'playing' && state.current === state.playerColor;

    for (let move = 0; move < SIZE * SIZE; move += 1) {
      const cell = cellEls[move];
      const value = state.board[move];
      const row = E.rowOf(move) + 1;
      const col = E.colOf(move) + 1;
      const base = `第 ${row} 行，第 ${col} 列`;
      cell.classList.toggle('occupied', value !== E.EMPTY);
      cell.setAttribute('aria-label', value === E.EMPTY ? base : `${base}，${STONE_LABEL[value]}`);
      cell.setAttribute('aria-disabled', canPlay && value === E.EMPTY ? 'false' : 'true');
      cell.tabIndex = move === state.focusMove ? 0 : -1;
    }
  }

  function updateUI() {
    const over = state.phase === 'over';
    const aiTurn = state.gameStarted && state.phase === 'ai';
    const playerTurn =
      state.gameStarted && state.phase === 'playing' && state.current === state.playerColor;

    els.board.classList.toggle('can-play', playerTurn);
    els.board.classList.toggle('player-black', state.current === E.BLACK);
    els.board.classList.toggle('player-white', state.current === E.WHITE);
    els.board.classList.toggle('is-over', over);
    els.board.setAttribute('aria-busy', aiTurn ? 'true' : 'false');

    let status = '准备开局';
    if (over) {
      status = state.winner === 0
        ? '平局'
        : state.winner === state.playerColor ? '你赢了' : '弈者获胜';
    } else if (aiTurn) {
      status = '弈者正在思考';
    } else if (playerTurn) {
      status = '轮到你落子';
    } else if (state.gameStarted) {
      status = '等待落子';
    }
    els.statusText.textContent = status;

    const stoneColor = over
      ? state.winner
      : state.gameStarted ? state.current : 0;
    els.statusStone.className = 'status-stone';
    if (stoneColor === E.BLACK) els.statusStone.classList.add('black');
    else if (stoneColor === E.WHITE) els.statusStone.classList.add('white');
    else els.statusStone.classList.add('is-empty');
    els.thinkingDots.hidden = !aiTurn;

    els.humanCard.classList.toggle('is-active', playerTurn);
    els.aiCard.classList.toggle('is-active', aiTurn);
    els.humanCard.classList.toggle('is-winner', over && state.winner === state.playerColor);
    els.aiCard.classList.toggle('is-winner', over && state.winner === state.aiColor);
    els.humanTurnPill.textContent = '落子中';
    els.aiTurnPill.textContent = '思考中';

    if (state.gameStarted) {
      els.humanColor.textContent = state.playerColor === E.BLACK ? '执黑 · 禁手' : '执白';
      els.aiColor.textContent = state.aiColor === E.BLACK ? '执黑 · 禁手' : '执白';
    } else {
      els.humanColor.textContent = '执黑';
      els.aiColor.textContent = '执白';
    }

    els.moveCount.textContent = String(state.history.length);
    els.matchState.textContent = over ? '已结束' : state.gameStarted ? '进行中' : '待开局';
    els.difficultyPill.textContent =
      E.DIFFICULTIES[state.gameStarted ? state.gameDifficulty : state.selectedDifficulty].label;

    const canUndo =
      playerTurn && state.history.some((entry) => entry.player === state.playerColor);
    els.undoBtn.disabled = !canUndo;
    els.restartBtn.disabled = aiTurn;

    const showResult = over && !state.resultDismissed && !state.resultDelay;
    els.boardResult.hidden = !showResult;

    syncCells();
    syncLastStone();
  }

  function startGame() {
    if (state.pendingFirst === null) return;

    window.clearTimeout(state.aiTimer);
    state.aiTimer = null;
    clearResultTimer();
    state.gameToken += 1;

    hideModal(els.setupModal);
    state.setupResumable = false;
    els.setupCloseBtn.hidden = true;

    state.gameStarted = true;
    state.gameDifficulty = state.selectedDifficulty;
    state.playerColor = state.pendingFirst ? E.BLACK : E.WHITE;
    state.aiColor = E.other(state.playerColor);
    state.pendingFirst = null;

    state.board = E.createBoard();
    state.history = [];
    state.current = E.BLACK;
    state.phase = 'playing';
    state.winner = 0;
    state.winLine = null;
    state.lastMove = -1;
    state.resultDismissed = false;
    state.resultDelay = false;
    state.focusMove = 6 * SIZE + 6;

    clearStones();
    clearWinMarks();
    els.boardResult.hidden = true;
    syncDifficultyUI();
    updateUI();

    showToast(state.playerColor === E.BLACK ? '你执黑先行' : '弈者执黑先行');

    if (state.current === state.aiColor) scheduleAI();
  }

  function placeMove(move, player) {
    if (!Number.isInteger(move) || move < 0 || move >= SIZE * SIZE) return false;
    if (state.board[move] !== E.EMPTY) return false;
    if (player === E.BLACK && !E.isLegalMove(state.board, move, player)) return false;

    state.board[move] = player;
    state.lastMove = move;
    const row = E.rowOf(move);
    const col = E.colOf(move);
    state.history.push({ move, row, col, player });
    addStoneElement(move, player, true);
    syncLastStone();

    const winLine = E.checkWin(state.board, move, player);
    if (winLine) {
      state.phase = 'over';
      state.winner = player;
      state.winLine = winLine;
      markWinningStones(winLine);
      drawWinLine(winLine);
      showResult(player);
      updateUI();
      return true;
    }

    if (E.isBoardFull(state.board)) {
      state.phase = 'over';
      state.winner = 0;
      state.winLine = null;
      showResult(0);
      updateUI();
      return true;
    }

    state.current = E.other(player);
    state.phase = 'playing';
    updateUI();
    return true;
  }

  function scheduleAI() {
    if (!state.gameStarted || state.phase === 'over') return;

    state.phase = 'ai';
    updateUI();
    const token = state.gameToken;
    window.clearTimeout(state.aiTimer);

    state.aiTimer = window.setTimeout(() => {
      if (token !== state.gameToken || state.phase !== 'ai') return;

      let result = null;
      try {
        result = E.chooseMove(state.board, state.aiColor, state.gameDifficulty);
      } catch (error) {
        console.error('AI 落子计算失败：', error);
      }

      if (token !== state.gameToken || state.phase !== 'ai') return;

      let move = result && Number.isInteger(result.move) ? result.move : -1;
      if (move < 0 || move >= SIZE * SIZE || state.board[move] !== E.EMPTY) {
        move = -1;
      }

      if (move >= 0) {
        const analysis = E.analyzeMove(state.board, move, state.aiColor);
        if (!analysis.legal) move = -1;
      }

      if (move < 0) {
        const legal = E.getAllLegalMoves(state.board, state.aiColor);
        move = legal.length > 0 ? legal[0] : -1;
      }

      state.aiTimer = null;

      if (move < 0) {
        if (E.isBoardFull(state.board)) {
          state.phase = 'over';
          state.winner = 0;
          state.winLine = null;
          showResult(0);
          updateUI();
        } else if (state.aiColor === E.BLACK) {
          state.phase = 'over';
          state.winner = state.playerColor;
          state.winLine = null;
          showResult(state.playerColor, 'noLegal');
          updateUI();
        }
        return;
      }

      placeMove(move, state.aiColor);
    }, 420);
  }

  function handleCellClick(move) {
    if (!state.gameStarted || state.phase !== 'playing') return;
    if (state.current !== state.playerColor) return;
    if (state.board[move] !== E.EMPTY) return;

    const analysis = E.analyzeMove(state.board, move, state.playerColor);
    if (!analysis.legal) {
      if (analysis.forbidden) showForbidden(move, analysis.reasons);
      return;
    }

    state.focusMove = move;
    const placed = placeMove(move, state.playerColor);
    if (placed && state.phase === 'playing') scheduleAI();
  }

  function undoMove() {
    if (!state.gameStarted || state.phase !== 'playing' || state.current !== state.playerColor) {
      return;
    }

    let lastPlayerIndex = -1;
    for (let i = state.history.length - 1; i >= 0; i -= 1) {
      if (state.history[i].player === state.playerColor) {
        lastPlayerIndex = i;
        break;
      }
    }
    if (lastPlayerIndex < 0) return;

    const removed = state.history.splice(lastPlayerIndex);
    for (const entry of removed) {
      state.board[entry.move] = E.EMPTY;
    }

    state.lastMove = state.history.length > 0
      ? state.history[state.history.length - 1].move
      : -1;
    state.current = state.playerColor;
    state.phase = 'playing';
    state.winner = 0;
    state.winLine = null;
    state.resultDismissed = false;
    state.resultDelay = false;
    clearResultTimer();
    clearWinMarks();
    els.boardResult.hidden = true;
    rebuildStones();
    updateUI();
    showToast('已悔棋，重新想想');
  }

  function showToast(message) {
    window.clearTimeout(state.toastTimer);
    els.toast.textContent = message;
    els.toast.classList.add('is-visible');
    state.toastTimer = window.setTimeout(() => {
      els.toast.classList.remove('is-visible');
    }, 1900);
  }

  function hideToast() {
    window.clearTimeout(state.toastTimer);
    els.toast.classList.remove('is-visible');
  }

  function flashForbidden(move) {
    const cell = cellEls[move];
    if (!cell) return;

    const oldMark = cell.querySelector('.forbidden-mark');
    if (oldMark) oldMark.remove();
    window.clearTimeout(cell._forbiddenTimer);

    const mark = document.createElement('span');
    mark.className = 'forbidden-mark';
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = '×';
    cell.appendChild(mark);
    void cell.offsetWidth;

    cell._forbiddenTimer = window.setTimeout(() => {
      mark.remove();
    }, 860);
  }

  function showForbidden(move, reasons) {
    const labels = (reasons && reasons.length > 0 ? reasons : ['forbidden'])
      .map((reason) => E.FORBIDDEN_LABELS[reason] || '禁手')
      .join('、');
    showToast(`${labels}禁手 · 黑棋不能落在这里`);
    flashForbidden(move);
  }

  function moveFocus(row, col) {
    if (row < 0 || row >= SIZE || col < 0 || col >= SIZE) return;
    const move = row * SIZE + col;
    state.focusMove = move;
    cellEls.forEach((cell, index) => {
      cell.tabIndex = index === move ? 0 : -1;
    });
    cellEls[move].focus({ preventScroll: true });
  }

  function bindEvents() {
    els.cells.addEventListener('click', (event) => {
      const cell = event.target.closest('.cell');
      if (!cell) return;
      handleCellClick(Number(cell.dataset.move));
    });

    els.cells.addEventListener('focusin', (event) => {
      const cell = event.target.closest('.cell');
      if (!cell) return;
      state.focusMove = Number(cell.dataset.move);
      cellEls.forEach((item, index) => {
        item.tabIndex = index === state.focusMove ? 0 : -1;
      });
    });

    els.cells.addEventListener('keydown', (event) => {
      const cell = event.target.closest('.cell');
      if (!cell) return;
      const row = Number(cell.dataset.row);
      const col = Number(cell.dataset.col);
      let nextRow = row;
      let nextCol = col;

      switch (event.key) {
        case 'ArrowUp':
        case 'w':
        case 'W':
          nextRow -= 1;
          break;
        case 'ArrowDown':
        case 's':
        case 'S':
          nextRow += 1;
          break;
        case 'ArrowLeft':
        case 'a':
        case 'A':
          nextCol -= 1;
          break;
        case 'ArrowRight':
        case 'd':
        case 'D':
          nextCol += 1;
          break;
        case 'Home':
          nextRow = 0;
          nextCol = 0;
          break;
        case 'End':
          nextRow = SIZE - 1;
          nextCol = SIZE - 1;
          break;
        default:
          return;
      }

      event.preventDefault();
      moveFocus(nextRow, nextCol);
    });

    els.difficultyList.addEventListener('click', (event) => {
      const option = event.target.closest('.difficulty-option');
      if (!option) return;
      selectDifficulty(option.dataset.level);
    });

    els.difficultyList.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
      const options = Array.from(els.difficultyList.querySelectorAll('.difficulty-option'));
      const currentIndex = options.findIndex((option) => option.classList.contains('is-active'));
      const direction = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
      const nextIndex = (currentIndex + direction + options.length) % options.length;
      event.preventDefault();
      selectDifficulty(options[nextIndex].dataset.level);
      options[nextIndex].focus();
    });

    els.rpsButtons.addEventListener('click', (event) => {
      const button = event.target.closest('button[data-gesture]');
      if (!button) return;
      playRPS(button.dataset.gesture);
    });

    els.startGameBtn.addEventListener('click', startGame);
    els.restartBtn.addEventListener('click', () => {
      if (state.phase === 'ai') return;
      openSetup();
    });
    els.undoBtn.addEventListener('click', undoMove);
    els.rematchBtn.addEventListener('click', openSetup);
    els.reviewBtn.addEventListener('click', hideResultOverlay);
    els.setupCloseBtn.addEventListener('click', closeSetup);
    els.rulesBtn.addEventListener('click', openRules);
    els.rulesCloseBtn.addEventListener('click', closeRules);
    els.rulesOkBtn.addEventListener('click', closeRules);

    els.setupModal.addEventListener('click', (event) => {
      if (event.target === els.setupModal) closeSetup();
    });
    els.rulesModal.addEventListener('click', (event) => {
      if (event.target === els.rulesModal) closeRules();
    });

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') return;
      if (!els.rulesModal.hidden) {
        closeRules();
        return;
      }
      if (!els.setupModal.hidden && state.setupResumable) {
        closeSetup();
      }
    });
  }

  function init() {
    drawBoardLines();
    buildCells();
    bindEvents();
    syncDifficultyUI();
    updateUI();
    openSetup();
  }

  init();
})();
