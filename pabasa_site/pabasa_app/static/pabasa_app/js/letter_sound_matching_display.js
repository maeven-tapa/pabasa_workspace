// Display only: retain stored phonics values for matching, submissions and audio paths.
window.formatLetterSoundMatchingItem = function (value, language = 'Filipino') {
    const text = String(value ?? '').trim();
    const normalizedLanguage = String(language || 'Filipino').trim().toLowerCase();
    return normalizedLanguage.startsWith('fil') || normalizedLanguage === 'tagalog'
        ? text.toLowerCase()
        : text;
};
