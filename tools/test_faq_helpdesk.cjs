const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {normalizeQuery, filterRecords, pageRecords} = require('../pabasa_site/pabasa_app/static/pabasa_app/js/faq_helpdesk.js');

const source = fs.readFileSync(path.join(__dirname, '../pabasa_site/pabasa_app/templates/pabasa_app/faq_questions.html'), 'utf8');
const plain = html => html.replace(/<[^>]*>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
// Exercise the real collection rather than maintaining a second set of answers.
const records = [...source.matchAll(/<article class="hd-question" id="([^"]+)" data-faq-record data-topic="([^"]+)" data-topic-label="([^"]+)" data-keywords="([^"]+)">([\s\S]*?)<\/article>/g)].map(match => ({
    id: match[1], topic: match[2], topicLabel: plain(match[3]), keywords: match[4],
    title: plain(match[5].match(/<span data-question-title>([\s\S]*?)<\/span>/)[1]),
    answer: plain(match[5].match(/<div class="hd-answer"[^>]*>([\s\S]*)<\/div>/)[1]),
}));

test('the real FAQ collection is unique and contains all three topics', () => {
    assert.equal(records.length, 19);
    assert.equal(new Set(records.map(record => record.id)).size, 19);
    assert.equal(filterRecords(records, '', 'getting-started').length, 4);
    assert.equal(filterRecords(records, '', 'reading').length, 10);
    assert.equal(filterRecords(records, '', 'accounts').length, 5);
});
test('normalizes case, extra whitespace, punctuation and accents', () => {
    assert.equal(normalizeQuery('  MICROPHONE!  '), 'microphone');
    assert.equal(normalizeQuery('  vérification\n code  '), 'verification code');
    assert.deepEqual(filterRecords(records, '  MICROPHONE!  '), filterRecords(records, 'microphone'));
    assert.deepEqual(filterRecords(records, '   '), records);
});
test('finds real question, answer, topic, and keyword content', () => {
    assert(filterRecords(records, 'microphone').some(record => record.id === 'help-oral-reading'));
    assert(filterRecords(records, 'PABASA ID').some(record => record.id === 'help-account-access'));
    assert(filterRecords(records, 'session 9 drawings').some(record => record.id === 'help-automatic-checking'));
    assert.equal(filterRecords(records, 'Getting Started').length, 4);
    assert(filterRecords(records, 'brownout').some(record => record.id === 'help-interrupted-assessment'));
});
test('all query terms must match, and topic filtering preserves the query', () => {
    const all = filterRecords(records, 'microphone');
    const accounts = filterRecords(records, 'microphone', 'accounts');
    assert(all.length > accounts.length);
    assert(accounts.every(record => record.topic === 'accounts' && all.includes(record)));
    assert.equal(filterRecords(records, 'purple giraffe').length, 0);
    assert.equal(filterRecords(records, '<script>alert(1)</script>').length, 0);
});
test('does not duplicate search results even with repeated input records', () => {
    assert.equal(filterRecords([...records, ...records], '').length, records.length);
});
test('pagination has no missing records, empty final page, or out-of-range state', () => {
    const pages = [0,1,2].map(page => pageRecords(records, page));
    assert.deepEqual(pages.flatMap(page => page.items), records);
    assert.deepEqual(pages.map(page => page.items.length), [8,8,3]);
    assert.equal(pageRecords(records, 999).page, 2);
    assert.equal(pageRecords(records, -1).page, 0);
    assert.deepEqual(pageRecords([], 5), {items: [], page: 0, pages: 1});
    assert.equal(pageRecords(filterRecords(records, '', 'accounts'), 3).page, 0);
});
test('every quick link resolves to one central record, and deep links reach later pages', () => {
    const template = fs.readFileSync(path.join(__dirname, '../pabasa_site/pabasa_app/templates/pabasa_app/faq.html'), 'utf8');
    for (const [,id] of template.matchAll(/data-quick-answer="([^"]+)"/g)) {
        assert.equal(records.filter(record => record.id === id).length, 1);
    }
    const reading = filterRecords(records, '', 'reading');
    const index = reading.findIndex(record => record.id === 'help-missing-progress');
    assert.equal(Math.floor(index / 8), 1);
    assert(pageRecords(reading, 1).items.some(record => record.id === 'help-missing-progress'));
});
