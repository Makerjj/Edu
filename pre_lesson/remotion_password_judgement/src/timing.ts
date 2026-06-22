import voiceoverDurationsRaw from "./voiceoverDurations.json";

export const fps = 30;

const voiceoverDurations = voiceoverDurationsRaw as Record<string, number>;

function secondsToFrames(seconds: number) {
  return Math.ceil(seconds * fps) + 18;
}

const openingScreenshotFrames = 5 * fps;

export const sceneDurations = {
  problem: openingScreenshotFrames,
  intro: secondsToFrames(Number(voiceoverDurations.intro ?? 32)),
  sample: secondsToFrames(Number(voiceoverDurations.sample ?? 40)),
  strategy: secondsToFrames(Number(voiceoverDurations.strategy ?? 38)),
  trace: secondsToFrames(Number(voiceoverDurations.trace ?? 34)),
  code: secondsToFrames(Number(voiceoverDurations.code ?? 42)),
  summary: secondsToFrames(Number(voiceoverDurations.summary ?? 28)),
};

export const sceneStarts = {
  problem: 0,
  intro: sceneDurations.problem,
  sample: sceneDurations.problem + sceneDurations.intro,
  strategy: sceneDurations.problem + sceneDurations.intro + sceneDurations.sample,
  trace:
    sceneDurations.problem +
    sceneDurations.intro +
    sceneDurations.sample +
    sceneDurations.strategy,
  code:
    sceneDurations.problem +
    sceneDurations.intro +
    sceneDurations.sample +
    sceneDurations.strategy +
    sceneDurations.trace,
  summary:
    sceneDurations.problem +
    sceneDurations.intro +
    sceneDurations.sample +
    sceneDurations.strategy +
    sceneDurations.trace +
    sceneDurations.code,
};

export const totalDurationInFrames =
  sceneDurations.problem +
  sceneDurations.intro +
  sceneDurations.sample +
  sceneDurations.strategy +
  sceneDurations.trace +
  sceneDurations.code +
  sceneDurations.summary;
