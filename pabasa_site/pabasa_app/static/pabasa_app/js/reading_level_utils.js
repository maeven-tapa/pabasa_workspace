(() => {
    const LEVEL_MULTIPLIERS = Object.freeze({
        vowel: 0.85,
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

    const DISCLAIMER = 'Great job completing your reading assessment! Your results show your current reading performance. Keep practicing to improve your reading skills.';

    const CLASSIFICATION_THRESHOLDS = Object.freeze([
        { threshold: 90, label: 'Readers at Grade Level' },
        { threshold: 80, label: 'Transitioning Readers' },
        { threshold: 70, label: 'Developing Readers' },
        { threshold: 60, label: 'High Emerging Readers' },
        { threshold: 0, label: 'Low Emerging Readers' },
    ]);

    function clampScore(score) {
        const numeric = Number(score);
        if (!Number.isFinite(numeric)) return 0;
        return Math.max(0, Math.min(100, numeric));
    }

    function normalizeAssessmentType(assessmentType) {
        const text = String(assessmentType || '').trim().toLowerCase();
        if (text.includes('vowel')) return 'vowel';
        if (text.includes('sentence')) return 'sentence';
        if (text.includes('paragraph')) return 'paragraph';
        return 'word';
    }

    function getLevelMultiplier(assessmentType) {
        return LEVEL_MULTIPLIERS[normalizeAssessmentType(assessmentType)] || LEVEL_MULTIPLIERS.word;
    }

    function getClassificationFromScore(totalScore) {
        const normalizedScore = clampScore(totalScore);
        const matched = CLASSIFICATION_THRESHOLDS.find(item => normalizedScore >= item.threshold) || CLASSIFICATION_THRESHOLDS[CLASSIFICATION_THRESHOLDS.length - 1];
        return matched.label;
    }

    function getPerformanceInterpretationFromScore(totalScore) {
        const normalizedScore = clampScore(totalScore);
        if (normalizedScore >= 85) return 'At Grade Level';
        if (normalizedScore >= 70) return 'Approaching Grade Level';
        if (normalizedScore >= 55) return 'Developing';
        if (normalizedScore >= 40) return 'Needs Support';
        return 'Needs Intensive Support';
    }

    function getFluencyScore(ratio, accuracy, isSkipped = false) {
        if (isSkipped) return 0;

        const normalizedAccuracy = clampScore(accuracy);
        let adjustedRatio = Math.max(0, Math.min(1, Number(ratio) || 0));
        if (normalizedAccuracy >= 95) adjustedRatio = Math.min(1, adjustedRatio + 0.18);
        else if (normalizedAccuracy >= 90) adjustedRatio = Math.min(1, adjustedRatio + 0.14);
        else if (normalizedAccuracy >= 80) adjustedRatio = Math.min(1, adjustedRatio + 0.08);
        else if (normalizedAccuracy >= 70) adjustedRatio = Math.min(1, adjustedRatio + 0.04);

        if (adjustedRatio <= 0.0) return 0;
        if (adjustedRatio >= 1.0) return 100;
        if (adjustedRatio >= 0.85) return 95;
        if (adjustedRatio >= 0.70) return 90;
        if (adjustedRatio >= 0.55) return 80;
        if (adjustedRatio >= 0.40) return 70;
        if (adjustedRatio >= 0.30) return 60;
        if (adjustedRatio >= 0.20) return 52;
        if (adjustedRatio >= 0.10) return 45;
        return 35;
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
        const scoreValue = student.final_score ?? student.total_score;
        if (scoreValue !== undefined && scoreValue !== null && scoreValue !== '') {
            return getClassificationFromScore(scoreValue);
        }
        const explicitLevel = student.adapted_reading_level || student.level || student.reading_level || student.classification || student.crla_classification;
        return normalizeReadingLevelLabel(explicitLevel) || explicitLevel || 'Pending';
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
        getClassificationFromScore,
        getPerformanceInterpretationFromScore,
        getFluencyScore,
        getReadingLevelFromScore,
        getReadingLevelLabel,
        normalizeAssessmentType,
        normalizeReadingLevelLabel,
    };
})();
