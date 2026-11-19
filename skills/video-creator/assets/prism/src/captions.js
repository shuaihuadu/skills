export async function loadCaptions(scenes) {
    return Promise.all(scenes.map(async (scene, index) => {
        if (!scene.narration.trim()) return [];
        const path = `../assets/audio/scene_${index + 1}.srt`;
        try {
            const response = await fetch(path);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const text = (await response.text()).trim().replace(/\r\n?/g, '\n');
            let previousEnd = 0;
            return text.split(/\n(?:[ \t]*\n)+/).map((block, cue) => {
                const [number, range, ...lines] = block.split('\n');
                const stamps = range?.split(/\s+-->\s+/) ?? [];
                const times = stamps.map(stamp => {
                    if (!/^\d{2,}:[0-5]\d:[0-5]\d,\d{3}$/.test(stamp)) return NaN;
                    const [hours, minutes, seconds, ms] = stamp.split(/[:,]/).map(Number);
                    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + ms;
                });
                const [start, end] = times;
                if (!/^\d+$/.test(number) || times.length !== 2 || !times.every(Number.isFinite) ||
                    !lines.join('').trim() || start < previousEnd || end <= start || end > scene.duration) {
                    throw new Error(`invalid subtitle cue ${cue + 1}`);
                }
                previousEnd = end;
                return { start, end, text: lines.join(' ') };
            });
        } catch (error) {
            throw new Error(`${path}: ${error.message}`);
        }
    }));
}