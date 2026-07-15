(() => {
    const LEVEL_MULTIPLIERS = Object.freeze({
        word: 0.90,
        sentence: 0.95,
        paragraph: 1.0,
    });

    const LEVEL_LABELS = Object.freeze([
        { threshold: 0.85, label: 'Readers at Grade Level' },
        { threshold: 0.70, label: 'Transitioning Readers' },
        { threshold: 0.55, label: 'Developing Readers' },
        { threshold: 0.40, label: 'High Emerging Readers' },
        { threshold: 0, label: 'Low Emerging Readers' },
    ]);

    const DISCLAIMER = 'Based on the finalized Total Score × Level Multiplier threshold mapping.';

    function clampScore(score) {
        const numeric = Number(score);
        if (!Number.isFinite(numeric)) return 0;
        return Math.max(0, Math.min(100, numeric));
    }

    function normalizeAssessmentType(assessmentType) {
        const text = String(assessmentType || '').trim().toLowerCase();
        if (text.includes('sentence')) return 'sentence';
        if (text.includes('paragraph')) return 'paragraph';
        return 'word';
    }

    function getLevelMultiplier(assessmentType) {
        return LEVEL_MULTIPLIERS[normalizeAssessmentType(assessmentType)] || LEVEL_MULTIPLIERS.word;
    }

    function getReadingLevelFromScore(totalScore, assessmentType) {
        const normalizedScore = clampScore(totalScore);
        const multiplier = getLevelMultiplier(assessmentType);
        const weightedScore = normalizedScore * multiplier;
        const normalizedLevelScore = Math.max(0, Math.min(100, weightedScore)) / 100;
        const matched = LEVEL_LABELS.find(item => normalizedLevelScore >= item.threshold) || LEVEL_LABELS[LEVEL_LABELS.length - 1];
        return {
            adapted_level_score: Math.round(normalizedLevelScore * 100) / 100,
            adapted_reading_level: matched.label,
            adapted_reading_level_disclaimer: DISCLAIMER,
        };
    }

    function getReadingLevelLabel(student) {
        if (!student || typeof student !== 'object') return 'Pending';
        const computed = getReadingLevelFromScore(student.total_score, student.assessment_type || student.assessmentType || student.mode);
        return computed.adapted_reading_level || student.adapted_reading_level || student.level || student.reading_level || student.classification || 'Pending';
    }

    function normalizeReadingLevelLabel(level) {
        const text = String(level || '').trim();
        if (!text) return 'Pending';
        const normalized = text.toLowerCase();
        if (normalized.includes('pending')) return 'Pending';
        if (normalized.includes('low') && normalized.includes('emerging')) return 'Low Emerging Readers';
        if (normalized.includes('high') && normalized.includes('emerging')) return 'High Emerging Readers';
        if (normalized.includes('develop')) return 'Developing Readers';
        if (normalized.includes('transition')) return 'Transitioning Readers';
        if (normalized.includes('grade') || normalized.includes('ready')) return 'Readers at Grade Level';
        return 'Pending';
    }

    window.PABASA_READING_LEVEL = {
        DISCLAIMER,
        clampScore,
        getLevelMultiplier,
        getReadingLevelFromScore,
        getReadingLevelLabel,
        normalizeAssessmentType,
        normalizeReadingLevelLabel,
    };
})();
