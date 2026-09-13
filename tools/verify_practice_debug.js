// Run the student Practice menu renderer with zero and threshold star balances.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname,
    '../pabasa_site/pabasa_app/templates/pabasa_app/practice.html'), 'utf8');
const script = template.split('<script>')[1].split('</script>')[0];
for (const [debug, stars, expectedOpen] of [
    [false, 0, 1], [true, 0, 3], [false, 0, 1], [false, 50, 2], [false, 150, 3],
]) {
    const grid = { innerHTML: '' };
    const starCounter = { textContent: '' };
    const context = {
        document: {
            getElementById: (id) => ({
                gameGrid: grid,
                challengeStars: starCounter,
                practiceMaterialsData: { textContent: '[{"id":1,"type":"word","is_done":false}]' },
            }[id] || null),
            querySelector: () => null,
            querySelectorAll: () => [],
            createElement: () => ({
                textContent: '',
                get innerHTML() { return this.textContent; },
            }),
        },
        window: { addEventListener() {} },
    };
    const rendered = script.replace(/{{\s*(.*?)\s*}}/g, (_, expression) => {
        if (expression.startsWith('practice_debug_unlock_all')) return String(debug);
        if (expression.startsWith('authoritative_total_stars_earned')) return String(stars);
        if (expression.startsWith('has_practice_language_preference')) return 'true';
        if (expression.startsWith('selected_practice_language')) return 'English';
        throw new Error(`Unhandled template expression: ${expression}`);
    });
    vm.runInNewContext(rendered, context);
    assert.equal((grid.innerHTML.match(/class="game-card is-active"/g) || []).length, expectedOpen);
    assert.equal((grid.innerHTML.match(/class="game-card is-locked"/g) || []).length, 3 - expectedOpen);
    assert.equal(Number(starCounter.textContent), stars);
    if (debug) assert.ok(!grid.innerHTML.includes('Unlock at'));
}
console.log('Practice menu: all 5 debug and star-threshold scenarios passed.');
