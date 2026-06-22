import React from "react";
import { Composition } from "remotion";
import { PasswordJudgementLesson } from "./PasswordJudgementLesson";
import { totalDurationInFrames } from "./timing";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PasswordJudgementLesson"
      component={PasswordJudgementLesson}
      durationInFrames={totalDurationInFrames}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
