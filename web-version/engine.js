(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.GomokuEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const SIZE = 14;
  const EMPTY = 0;
  const BLACK = 1;
  const WHITE = 2;
  const WIN_SCORE = 1000000000;
  const DIRECTIONS = Object.freeze([
    [0, 1],   // horizontal
    [1, 0],   // vertical
    [1, 1],   // diagonal down-right
    [1, -1],  // diagonal down-left
  ]);

  const DIFFICULTIES = Object.freeze({
    easy: {
      id: 'easy',
      label: '简单',
      tagline: '轻松热身',
      description: '落子随性，偶尔会漏看你的杀招。',
    },
    medium: {
      id: 'medium',
      label: '中等',
      tagline: '认真对弈',
      description: '会攻会守，能识别四连与常见陷阱。',
    },
    hard: {
      id: 'hard',
      label: '困难',
      tagline: '步步紧逼',
      description: '预判数步之后的局面，擅长制造双重威胁。',
    },
  });

  const CENTER_POINTS = Object.freeze([
    6 * SIZE + 6,
    6 * SIZE + 7,
    7 * SIZE + 6,
    7 * SIZE + 7,
  ]);

  const FORBIDDEN_LABELS = Object.freeze({
    overline: '长连',
    doubleFour: '四四',
    doubleThree: '三三',
  });

  const PATTERN_GROUPS = [
    { key: 'five', source: '11111' },
    { key: 'openFour', source: '011110' },
    { key: 'four', source: '11110|01111|11011|10111|11101' },
    { key: 'openThree', source: '01110|010110|011010' },
    { key: 'three', source: '11100|00111|11010|01011|10110|01101|10011|11001|10101' },
    { key: 'openTwo', source: '001100|011000|000110|010100|001010|010010' },
    { key: 'two', source: '11000|00011|10100|00101|10010|01001' },
  ];
  const PATTERN_REGEXES = PATTERN_GROUPS.map((group) => ({
    key: group.key,
    regex: new RegExp(group.source, 'g'),
  }));

  const EMPTY_SHAPES = Object.freeze({
    five: 0,
    openFour: 0,
    four: 0,
    openThree: 0,
    three: 0,
    openTwo: 0,
    two: 0,
  });

  // All straight lines of at least five intersections, precomputed for the
  // static board evaluation used by the hard AI.
  const LINES = (function buildLines() {
    const lines = [];
    const add = (cells) => {
      if (cells.length >= 5) lines.push(cells);
    };

    for (let r = 0; r < SIZE; r += 1) {
      const cells = [];
      for (let c = 0; c < SIZE; c += 1) cells.push(r * SIZE + c);
      add(cells);
    }
    for (let c = 0; c < SIZE; c += 1) {
      const cells = [];
      for (let r = 0; r < SIZE; r += 1) cells.push(r * SIZE + c);
      add(cells);
    }

    // Diagonals running down-right.
    for (let c = 0; c < SIZE; c += 1) {
      const cells = [];
      for (let r = 0, cc = c; r < SIZE && cc < SIZE; r += 1, cc += 1) {
        cells.push(r * SIZE + cc);
      }
      add(cells);
    }
    for (let r = 1; r < SIZE; r += 1) {
      const cells = [];
      for (let rr = r, c = 0; rr < SIZE && c < SIZE; rr += 1, c += 1) {
        cells.push(rr * SIZE + c);
      }
      add(cells);
    }

    // Diagonals running down-left.
    for (let c = 0; c < SIZE; c += 1) {
      const cells = [];
      for (let r = 0, cc = c; r < SIZE && cc >= 0; r += 1, cc -= 1) {
        cells.push(r * SIZE + cc);
      }
      add(cells);
    }
    for (let r = 1; r < SIZE; r += 1) {
      const cells = [];
      for (let rr = r, c = SIZE - 1; rr < SIZE && c >= 0; rr += 1, c -= 1) {
        cells.push(rr * SIZE + c);
      }
      add(cells);
    }

    return lines;
  })();

  function other(player) {
    return player === BLACK ? WHITE : BLACK;
  }

  function createBoard() {
    return new Array(SIZE * SIZE).fill(EMPTY);
  }

  function rowOf(move) {
    return Math.floor(move / SIZE);
  }

  function colOf(move) {
    return move % SIZE;
  }

  function inBounds(row, col) {
    return row >= 0 && row < SIZE && col >= 0 && col < SIZE;
  }

  function boardStoneCount(board) {
    let count = 0;
    for (let i = 0; i < board.length; i += 1) {
      if (board[i] !== EMPTY) count += 1;
    }
    return count;
  }

  function buildRunAt(board, move, player, dr, dc) {
    const row = rowOf(move);
    const col = colOf(move);
    const line = [move];

    for (let step = 1; step < SIZE; step += 1) {
      const r = row + dr * step;
      const c = col + dc * step;
      if (!inBounds(r, c) || board[r * SIZE + c] !== player) break;
      line.push(r * SIZE + c);
    }
    for (let step = 1; step < SIZE; step += 1) {
      const r = row - dr * step;
      const c = col - dc * step;
      if (!inBounds(r, c) || board[r * SIZE + c] !== player) break;
      line.unshift(r * SIZE + c);
    }

    return line;
  }

  function getRunsAt(board, move, player) {
    return DIRECTIONS.map(([dr, dc]) => buildRunAt(board, move, player, dr, dc));
  }

  /**
   * Black wins only by making exactly five. White may win with five or an
   * overline. A black five takes precedence over any simultaneous foul.
   */
  function winningLineFor(board, move, player) {
    if (!Number.isInteger(move) || move < 0 || move >= SIZE * SIZE) return null;
    if (board[move] !== player) return null;

    let bestLine = null;
    for (const run of getRunsAt(board, move, player)) {
      const isWin = player === BLACK ? run.length === 5 : run.length >= 5;
      if (isWin && (!bestLine || run.length > bestLine.length)) bestLine = run;
    }
    return bestLine;
  }

  /**
   * Return every cell in the winning run that contains `lastMove`, or null.
   */
  function checkWin(board, lastMove, player) {
    return winningLineFor(board, lastMove, player);
  }

  function wouldWinAt(board, move, player) {
    const wasEmpty = board[move] === EMPTY;
    if (!wasEmpty && board[move] !== player) return false;
    if (wasEmpty) board[move] = player;

    const win = winningLineFor(board, move, player) !== null;

    if (wasEmpty) board[move] = EMPTY;
    return win;
  }

  function isStraightFourRun(board, run, dr, dc, player) {
    if (run.length !== 4) return false;

    const first = run[0];
    const last = run[run.length - 1];
    const beforeRow = rowOf(first) - dr;
    const beforeCol = colOf(first) - dc;
    const afterRow = rowOf(last) + dr;
    const afterCol = colOf(last) + dc;

    if (!inBounds(beforeRow, beforeCol) || !inBounds(afterRow, afterCol)) return false;
    if (board[beforeRow * SIZE + beforeCol] !== EMPTY) return false;
    if (board[afterRow * SIZE + afterCol] !== EMPTY) return false;

    // Adding a stone at either end must make exactly five, not an overline.
    const beforeTwoRow = beforeRow - dr;
    const beforeTwoCol = beforeCol - dc;
    const afterTwoRow = afterRow + dr;
    const afterTwoCol = afterCol + dc;
    if (
      inBounds(beforeTwoRow, beforeTwoCol) &&
      board[beforeTwoRow * SIZE + beforeTwoCol] === player
    ) {
      return false;
    }
    if (
      inBounds(afterTwoRow, afterTwoCol) &&
      board[afterTwoRow * SIZE + afterTwoCol] === player
    ) {
      return false;
    }

    return true;
  }

  /**
   * Count distinct fours created by the stone on `move`. Completion points
   * that would create an overline do not count as a four.
   */
  function countFoursAt(board, move, player) {
    const signatures = new Set();
    const row = rowOf(move);
    const col = colOf(move);

    for (const [dr, dc] of DIRECTIONS) {
      for (let step = -4; step <= 4; step += 1) {
        if (step === 0) continue;
        const r = row + dr * step;
        const c = col + dc * step;
        if (!inBounds(r, c)) continue;

        const completion = r * SIZE + c;
        if (board[completion] !== EMPTY) continue;

        board[completion] = player;
        const run = buildRunAt(board, completion, player, dr, dc);
        if (run.length === 5 && run.includes(move)) {
          const four = run.filter((cell) => cell !== completion).sort((a, b) => a - b);
          signatures.add(four.join(','));
        }
        board[completion] = EMPTY;
      }
    }

    return signatures.size;
  }

  /**
   * Count distinct open threes created by the stone on `move`. A three only
   * counts when it can become a straight four without making five, an
   * overline, or a double-four at the extension point.
   */
  function countThreesAt(board, move, player) {
    const signatures = new Set();
    const row = rowOf(move);
    const col = colOf(move);

    for (const [dr, dc] of DIRECTIONS) {
      for (let step = -4; step <= 4; step += 1) {
        if (step === 0) continue;
        const r = row + dr * step;
        const c = col + dc * step;
        if (!inBounds(r, c)) continue;

        const extension = r * SIZE + c;
        if (board[extension] !== EMPTY) continue;

        board[extension] = player;
        const run = buildRunAt(board, extension, player, dr, dc);
        if (run.length === 4 && run.includes(move) && isStraightFourRun(board, run, dr, dc, player)) {
          const runsAtExtension = getRunsAt(board, extension, player);
          const createsFive = runsAtExtension.some((item) => item.length === 5);
          const createsOverline = runsAtExtension.some((item) => item.length >= 6);
          const createsDoubleFour = countFoursAt(board, extension, player) >= 2;

          if (!createsFive && !createsOverline && !createsDoubleFour) {
            const three = run
              .filter((cell) => cell !== extension)
              .sort((a, b) => a - b);
            signatures.add(three.join(','));
          }
        }
        board[extension] = EMPTY;
      }
    }

    return signatures.size;
  }

  function hasOverlineAt(board, move, player) {
    return getRunsAt(board, move, player).some((run) => run.length >= 6);
  }

  /**
   * Evaluate a move for the current rules. Black may not play an overline,
   * double-four or double-three. A black move making exactly five is always
   * allowed and wins even if it also creates a forbidden shape.
   */
  function analyzeMove(board, move, player) {
    const result = {
      move,
      player,
      legal: false,
      winning: false,
      forbidden: false,
      reasons: [],
      winLine: null,
      overline: false,
      fours: 0,
      threes: 0,
    };

    if (!Number.isInteger(move) || move < 0 || move >= SIZE * SIZE) return result;
    if (board[move] !== EMPTY) return result;

    board[move] = player;
    const winLine = winningLineFor(board, move, player);

    if (winLine) {
      result.legal = true;
      result.winning = true;
      result.winLine = winLine;
    } else if (player === WHITE) {
      result.legal = true;
    } else {
      const overline = hasOverlineAt(board, move, player);
      const fours = countFoursAt(board, move, player);
      const threes = countThreesAt(board, move, player);

      result.overline = overline;
      result.fours = fours;
      result.threes = threes;
      if (overline) result.reasons.push('overline');
      if (fours >= 2) result.reasons.push('doubleFour');
      if (threes >= 2) result.reasons.push('doubleThree');
      result.forbidden = result.reasons.length > 0;
      result.legal = !result.forbidden;
    }

    board[move] = EMPTY;
    return result;
  }

  function isLegalMove(board, move, player) {
    if (!Number.isInteger(move) || move < 0 || move >= SIZE * SIZE) return false;
    if (board[move] !== EMPTY) return false;
    if (player === WHITE) return true;

    board[move] = player;
    if (winningLineFor(board, move, player)) {
      board[move] = EMPTY;
      return true;
    }
    if (hasOverlineAt(board, move, player)) {
      board[move] = EMPTY;
      return false;
    }
    if (countFoursAt(board, move, player) >= 2) {
      board[move] = EMPTY;
      return false;
    }
    const legal = countThreesAt(board, move, player) < 2;
    board[move] = EMPTY;
    return legal;
  }

  function getLegalMoves(board, player, pool) {
    const candidates = pool || getCandidates(board, 2);
    return candidates.filter(
      (move) => board[move] === EMPTY && isLegalMove(board, move, player)
    );
  }

  function getAllLegalMoves(board, player) {
    const moves = [];
    for (let move = 0; move < SIZE * SIZE; move += 1) {
      if (board[move] !== EMPTY) continue;
      if (isLegalMove(board, move, player)) moves.push(move);
    }
    return moves;
  }

  function isBoardFull(board) {
    for (let i = 0; i < board.length; i += 1) {
      if (board[i] === EMPTY) return false;
    }
    return true;
  }

  /**
   * Empty cells within `radius` of an existing stone. Any cell that could
   * complete a line must touch a stone, so this is sufficient for tactics.
   */
  function getCandidates(board, radius) {
    const reach = radius == null ? 2 : radius;
    const seen = new Uint8Array(SIZE * SIZE);
    const candidates = [];
    let stones = 0;

    for (let i = 0; i < board.length; i += 1) {
      if (board[i] === EMPTY) continue;
      stones += 1;
      const row = rowOf(i);
      const col = colOf(i);
      for (let dr = -reach; dr <= reach; dr += 1) {
        for (let dc = -reach; dc <= reach; dc += 1) {
          if (dr === 0 && dc === 0) continue;
          const r = row + dr;
          const c = col + dc;
          if (!inBounds(r, c)) continue;
          const index = r * SIZE + c;
          if (board[index] === EMPTY && seen[index] === 0) {
            seen[index] = 1;
            candidates.push(index);
          }
        }
      }
    }

    if (stones === 0) return CENTER_POINTS.slice();
    return candidates;
  }

  function immediateWinningMoves(board, player, pool) {
    const candidates = pool || getCandidates(board, 2);
    const winning = [];
    for (const move of candidates) {
      if (board[move] !== EMPTY) continue;
      if (wouldWinAt(board, move, player)) winning.push(move);
    }
    return winning;
  }

  function lineStringFor(board, row, col, dr, dc, player) {
    let line = '';
    for (let step = -5; step <= 5; step += 1) {
      const r = row + dr * step;
      const c = col + dc * step;
      if (!inBounds(r, c)) {
        line += '2';
        continue;
      }
      const value = board[r * SIZE + c];
      line += value === EMPTY ? '0' : value === player ? '1' : '2';
    }
    return line;
  }

  function patternCoversCenter(line, regex) {
    regex.lastIndex = 0;
    let match;
    while ((match = regex.exec(line)) !== null) {
      if (match.index <= 5 && match.index + match[0].length > 5) return true;
      if (match.index === regex.lastIndex) regex.lastIndex += 1;
    }
    return false;
  }

  function classifyDirection(line) {
    for (const item of PATTERN_REGEXES) {
      if (patternCoversCenter(line, item.regex)) return item.key;
    }
    return null;
  }

  function shapeScore(shapes) {
    if (shapes.five > 0) return WIN_SCORE;

    let score = 0;
    if (shapes.openFour > 0) score += 7000000;
    if (shapes.four > 0) score += shapes.four === 1 ? 350000 : 5000000;
    if (shapes.openThree > 0) score += shapes.openThree === 1 ? 80000 : 1700000;
    if (shapes.four > 0 && shapes.openThree > 0) score += 2200000;
    score += shapes.three * 4500;
    score += shapes.openTwo * 650;
    score += shapes.two * 55;
    return score;
  }

  /** Pattern-based value of putting `player` on `move`. */
  function placementScore(board, move, player) {
    board[move] = player;
    const shapes = Object.assign({}, EMPTY_SHAPES);
    const row = rowOf(move);
    const col = colOf(move);

    for (const [dr, dc] of DIRECTIONS) {
      const line = lineStringFor(board, row, col, dr, dc, player);
      const shape = classifyDirection(line);
      if (shape) shapes[shape] += 1;
    }
    board[move] = EMPTY;

    const centerDistance = Math.max(Math.abs(row - 6.5), Math.abs(col - 6.5));
    return shapeScore(shapes) + Math.max(0, 7 - centerDistance) * 3;
  }

  function rankMoves(board, player, limit, pool) {
    const candidates = pool || getCandidates(board, 2);
    const opponent = other(player);
    const scored = candidates.map((move) => {
      const attack = placementScore(board, move, player);
      const defense = placementScore(board, move, opponent);
      return { move, score: attack + defense * 0.88 };
    });
    scored.sort((a, b) => b.score - a.score);

    if (player === WHITE) {
      return scored.slice(0, limit).map((entry) => entry.move);
    }

    const legal = [];
    for (const entry of scored) {
      if (legal.length >= limit) break;
      if (isLegalMove(board, entry.move, player)) legal.push(entry.move);
    }
    return legal;
  }

  // A cheaper heuristic used for move ordering inside the game tree.
  function quickPointScore(board, move, player) {
    board[move] = player;
    const row = rowOf(move);
    const col = colOf(move);
    let score = 0;

    for (const [dr, dc] of DIRECTIONS) {
      let count = 1;
      let openEnds = 0;

      for (const sign of [-1, 1]) {
        let step = 1;
        while (step < SIZE) {
          const r = row + dr * step * sign;
          const c = col + dc * step * sign;
          if (!inBounds(r, c) || board[r * SIZE + c] !== player) break;
          count += 1;
          step += 1;
        }
        const r = row + dr * step * sign;
        const c = col + dc * step * sign;
        if (inBounds(r, c) && board[r * SIZE + c] === EMPTY) openEnds += 1;
      }

      const capped = Math.min(count, 5);
      const base = [0, 1, 12, 160, 6000, 1000000][capped];
      const openMultiplier = openEnds === 2 ? 2.2 : openEnds === 1 ? 1 : 0.12;
      score += base * openMultiplier;
    }

    board[move] = EMPTY;
    return score;
  }

  function quickRankMoves(board, player, limit, pool) {
    const opponent = other(player);
    const scored = pool.map((move) => {
      const attack = quickPointScore(board, move, player);
      const defense = quickPointScore(board, move, opponent);
      return { move, score: attack + defense * 0.92 };
    });
    scored.sort((a, b) => b.score - a.score);

    if (player === WHITE) {
      return scored.slice(0, limit).map((entry) => entry.move);
    }

    const legal = [];
    const checkLimit = Math.min(scored.length, limit * 4);
    for (let i = 0; i < checkLimit && legal.length < limit; i += 1) {
      const move = scored[i].move;
      if (isLegalMove(board, move, player)) legal.push(move);
    }
    return legal;
  }

  function addRun(stats, length, openEnds) {
    if (length >= 5) {
      stats.five += 1;
    } else if (length === 4) {
      if (openEnds >= 2) stats.openFour += 1;
      else if (openEnds === 1) stats.four += 1;
    } else if (length === 3) {
      if (openEnds >= 2) stats.openThree += 1;
      else if (openEnds === 1) stats.three += 1;
    } else if (length === 2) {
      if (openEnds >= 2) stats.openTwo += 1;
      else if (openEnds === 1) stats.two += 1;
    }
  }

  function scoreStats(stats) {
    if (stats.five > 0) return WIN_SCORE;

    let score = 0;
    score += stats.openFour * 5000000;
    score += stats.four * 280000;
    score += stats.openThree * 65000;
    score += stats.three * 4500;
    score += stats.openTwo * 700;
    score += stats.two * 70;

    if (stats.four >= 2) score += 3600000;
    if (stats.four > 0 && stats.openThree > 0) score += 1800000;
    if (stats.openThree >= 2) score += 700000;
    return score;
  }

  function evaluateBoard(board, aiPlayer) {
    const human = other(aiPlayer);
    const aiStats = { five: 0, openFour: 0, four: 0, openThree: 0, three: 0, openTwo: 0, two: 0 };
    const humanStats = { five: 0, openFour: 0, four: 0, openThree: 0, three: 0, openTwo: 0, two: 0 };

    for (const line of LINES) {
      let i = 0;
      while (i < line.length) {
        const value = board[line[i]];
        if (value === EMPTY) {
          i += 1;
          continue;
        }

        let end = i + 1;
        while (end < line.length && board[line[end]] === value) end += 1;

        const before = i > 0 ? board[line[i - 1]] : -1;
        const after = end < line.length ? board[line[end]] : -1;
        const openEnds = (before === EMPTY ? 1 : 0) + (after === EMPTY ? 1 : 0);
        addRun(value === aiPlayer ? aiStats : humanStats, end - i, openEnds);
        i = end;
      }
    }

    return scoreStats(aiStats) - scoreStats(humanStats) * 1.08;
  }

  function widthForDepth(depth) {
    if (depth >= 4) return 8;
    if (depth === 3) return 7;
    if (depth === 2) return 6;
    return 5;
  }

  function minimax(board, turn, depth, alpha, beta, lastMove, lastPlayer, aiPlayer, ply) {
    if (lastMove >= 0 && lastPlayer && wouldWinAt(board, lastMove, lastPlayer)) {
      return lastPlayer === aiPlayer ? WIN_SCORE - ply : -WIN_SCORE + ply;
    }

    const candidates = getCandidates(board, 2);
    if (candidates.length === 0) return 0;

    const myWins = immediateWinningMoves(board, turn, candidates);
    if (myWins.length > 0) {
      return turn === aiPlayer ? WIN_SCORE - ply : -WIN_SCORE + ply;
    }

    if (depth <= 0) return evaluateBoard(board, aiPlayer);

    const opponent = other(turn);
    const opponentWins = immediateWinningMoves(board, opponent, candidates);
    const pool = opponentWins.length > 0 ? opponentWins : candidates;
    const width = widthForDepth(depth);
    let moves = quickRankMoves(board, turn, width, pool);
    if (moves.length === 0 && pool !== candidates) {
      moves = quickRankMoves(board, turn, width, candidates);
    }
    if (moves.length === 0) {
      const legal = getAllLegalMoves(board, turn);
      if (legal.length === 0) {
        if (turn === BLACK) {
          return turn === aiPlayer ? -WIN_SCORE + ply : WIN_SCORE - ply;
        }
        return 0;
      }
      moves = legal.slice(0, width);
    }

    if (turn === aiPlayer) {
      let best = -Infinity;
      for (const move of moves) {
        board[move] = turn;
        const value = minimax(
          board, opponent, depth - 1, alpha, beta, move, turn, aiPlayer, ply + 1
        );
        board[move] = EMPTY;
        if (value > best) best = value;
        if (best > alpha) alpha = best;
        if (alpha >= beta) break;
      }
      return best;
    }

    let best = Infinity;
    for (const move of moves) {
      board[move] = turn;
      const value = minimax(
        board, aiPlayer, depth - 1, alpha, beta, move, turn, aiPlayer, ply + 1
      );
      board[move] = EMPTY;
      if (value < best) best = value;
      if (best < beta) beta = best;
      if (alpha >= beta) break;
    }
    return best;
  }

  function randomOf(items) {
    return items[Math.floor(Math.random() * items.length)];
  }

  function openingMove(board) {
    if (boardStoneCount(board) === 0) return randomOf(CENTER_POINTS);
    return null;
  }

  function filterLegalCandidates(board, player, candidates) {
    if (player === WHITE) return candidates;
    const legal = candidates.filter((move) => isLegalMove(board, move, player));
    if (legal.length > 0) return legal;
    return getAllLegalMoves(board, player);
  }

  function chooseEasy(board, aiPlayer) {
    const opening = openingMove(board);
    if (opening !== null) return opening;

    const candidates = getCandidates(board, 2);
    if (candidates.length === 0) return -1;

    const wins = immediateWinningMoves(board, aiPlayer, candidates);
    if (wins.length > 0) return randomOf(wins);

    const legalCandidates = filterLegalCandidates(board, aiPlayer, candidates);
    if (legalCandidates.length === 0) return -1;

    const blocks = immediateWinningMoves(board, other(aiPlayer), candidates)
      .filter((move) => isLegalMove(board, move, aiPlayer));
    if (blocks.length > 0 && Math.random() < 0.58) return randomOf(blocks);

    // Easy mode mostly plays in the neighbourhood, but with a generous dose
    // of randomness so that beginners can create their own threats.
    if (Math.random() < 0.42) return randomOf(legalCandidates);

    const ranked = rankMoves(board, aiPlayer, 10, legalCandidates);
    if (ranked.length === 0) return legalCandidates[0];
    const pickFrom = ranked.slice(0, Math.min(4, ranked.length));
    return randomOf(pickFrom);
  }

  function chooseMedium(board, aiPlayer) {
    const opening = openingMove(board);
    if (opening !== null) return opening;

    const candidates = getCandidates(board, 2);
    if (candidates.length === 0) return -1;

    const wins = immediateWinningMoves(board, aiPlayer, candidates);
    if (wins.length > 0) return randomOf(wins);

    const legalCandidates = filterLegalCandidates(board, aiPlayer, candidates);
    const blocks = immediateWinningMoves(board, other(aiPlayer), candidates)
      .filter((move) => isLegalMove(board, move, aiPlayer));
    if (blocks.length > 0) {
      if (blocks.length === 1) return blocks[0];
      return rankMoves(board, aiPlayer, 1, blocks)[0] ?? blocks[0];
    }

    if (legalCandidates.length === 0) return -1;
    const ranked = rankMoves(board, aiPlayer, 6, legalCandidates);
    if (ranked.length === 0) return legalCandidates[0];
    // A little variety keeps repeat games fresh without making it careless.
    return Math.random() < 0.14 && ranked.length > 1 ? ranked[1] : ranked[0];
  }

  function chooseHard(board, aiPlayer) {
    const opening = openingMove(board);
    if (opening !== null) return opening;

    const candidates = getCandidates(board, 2);
    if (candidates.length === 0) return -1;

    const legalCandidates = filterLegalCandidates(board, aiPlayer, candidates);
    if (legalCandidates.length === 0) return -1;

    const wins = immediateWinningMoves(board, aiPlayer, candidates);
    if (wins.length > 0) return randomOf(wins);

    const human = other(aiPlayer);
    const blocks = immediateWinningMoves(board, human, candidates)
      .filter((move) => isLegalMove(board, move, aiPlayer));
    const pool = blocks.length > 0 ? blocks : legalCandidates;
    const rootMoves = rankMoves(board, aiPlayer, 12, pool);
    if (rootMoves.length === 0) return legalCandidates[0];

    let bestScore = -Infinity;
    let bestMoves = [];

    for (const move of rootMoves) {
      board[move] = aiPlayer;
      const score = minimax(board, human, 4, -Infinity, Infinity, move, aiPlayer, aiPlayer, 1);
      board[move] = EMPTY;

      if (score > bestScore) {
        bestScore = score;
        bestMoves = [move];
      } else if (score === bestScore) {
        bestMoves.push(move);
      }
    }

    if (bestMoves.length === 0) return rootMoves[0];
    return randomOf(bestMoves);
  }

  /**
   * Pick an AI move. Returns -1 when the board has no legal move.
   */
  function chooseMove(board, aiPlayer, difficulty) {
    const level = DIFFICULTIES[difficulty] ? difficulty : 'medium';
    let move;

    if (level === 'easy') move = chooseEasy(board, aiPlayer);
    else if (level === 'hard') move = chooseHard(board, aiPlayer);
    else move = chooseMedium(board, aiPlayer);

    if (
      move < 0 ||
      move >= SIZE * SIZE ||
      board[move] !== EMPTY ||
      !isLegalMove(board, move, aiPlayer)
    ) {
      const fallback = getAllLegalMoves(board, aiPlayer);
      move = fallback.length > 0 ? fallback[0] : -1;
    }

    return {
      move,
      row: move >= 0 ? rowOf(move) : -1,
      col: move >= 0 ? colOf(move) : -1,
      difficulty: level,
    };
  }

  return Object.freeze({
    SIZE,
    EMPTY,
    BLACK,
    WHITE,
    WIN_SCORE,
    DIRECTIONS,
    DIFFICULTIES,
    FORBIDDEN_LABELS,
    createBoard,
    rowOf,
    colOf,
    inBounds,
    other,
    checkWin,
    wouldWinAt,
    isBoardFull,
    getCandidates,
    immediateWinningMoves,
    analyzeMove,
    isLegalMove,
    getLegalMoves,
    getAllLegalMoves,
    placementScore,
    evaluateBoard,
    chooseMove,
  });
});
