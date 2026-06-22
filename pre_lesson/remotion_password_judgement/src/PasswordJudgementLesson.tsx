import React, { type CSSProperties } from "react";
import { AbsoluteFill, Audio, Sequence, interpolate, spring, staticFile, useCurrentFrame } from "remotion";
import { lessonData } from "./lessonData";
import voiceover from "./voiceover.json";
import { fps, sceneDurations, sceneStarts } from "./timing";

const colors = {
  bg: "#f4f6f8",
  ink: "#172033",
  muted: "#667085",
  panel: "#ffffff",
  border: "#d9e2ec",
  blue: "#2563eb",
  green: "#0f8a5f",
  red: "#dc2626",
  amber: "#b7791f",
  violet: "#7c3aed",
  softBlue: "#eff6ff",
  softGreen: "#ecfdf5",
  softRed: "#fef2f2",
  softAmber: "#fff7ed",
  softViolet: "#f5f3ff",
  header: "#151a22",
};

const codeFont = "Menlo, Monaco, Consolas, monospace";

const shell: CSSProperties = {
  background: colors.bg,
  color: colors.ink,
  fontFamily:
    'PingFang SC, "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif',
};

function fade(frame: number, start: number, duration = 14) {
  const p = interpolate(frame, [start, start + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return {
    opacity: p,
    transform: `translateY(${(1 - p) * 14}px)`,
  };
}

function Header({ active }: { active: number }) {
  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 116,
        background: colors.header,
        color: "#f8fafc",
        display: "flex",
        alignItems: "center",
        padding: "0 42px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          width: 360,
          height: 52,
          borderRadius: 8,
          background: "#26303c",
          display: "flex",
          alignItems: "center",
          padding: "0 22px",
          boxSizing: "border-box",
          fontSize: 27,
          fontWeight: 800,
        }}
      >
        {lessonData.title}
      </div>
      <div style={{ display: "flex", gap: 10, marginLeft: 50, flexWrap: "wrap" }}>
        {lessonData.steps.map((name, index) => (
          <div
            key={name}
            style={{
              minWidth: 76,
              height: 38,
              borderRadius: 8,
              padding: "0 12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: index === active ? colors.blue : "#3e4652",
              color: "#fff",
              fontSize: 16,
              fontWeight: 700,
            }}
          >
            {index + 1} {name}
          </div>
        ))}
      </div>
    </div>
  );
}

function Panel({
  x,
  y = 142,
  w,
  h = 792,
  title,
  accent,
  children,
}: {
  x: number;
  y?: number;
  w: number;
  h?: number;
  title: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width: w,
        height: h,
        borderRadius: 8,
        background: colors.panel,
        border: `1px solid ${colors.border}`,
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 8, background: accent }} />
      <div style={{ padding: "22px 24px 24px 28px", boxSizing: "border-box", height: "100%" }}>
        <div style={{ fontSize: 29, fontWeight: 800, marginBottom: 16 }}>{title}</div>
        <div style={{ borderTop: "1px solid #e6edf4", marginBottom: 18 }} />
        {children}
      </div>
    </div>
  );
}

function CodeBox({ children, fontSize = 34 }: { children: React.ReactNode; fontSize?: number }) {
  return (
    <div
      style={{
        borderRadius: 8,
        background: "#0f172a",
        color: "#f8fafc",
        padding: "20px 24px",
        fontFamily: codeFont,
        fontSize,
        lineHeight: 1.45,
        whiteSpace: "pre-wrap",
      }}
    >
      {children}
    </div>
  );
}

function ProblemScene() {
  return (
    <AbsoluteFill style={shell}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          padding: "34px 44px",
          boxSizing: "border-box",
          background: "#ffffff",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontSize: 48, fontWeight: 900 }}>{lessonData.problem.title}</div>
          <div style={{ display: "flex", gap: 12 }}>
            {lessonData.problem.meta.map((item) => (
              <div
                key={item}
                style={{
                  height: 42,
                  borderRadius: 8,
                  padding: "0 14px",
                  display: "flex",
                  alignItems: "center",
                  background: colors.softBlue,
                  color: colors.blue,
                  border: "1px solid #bfdbfe",
                  fontSize: 20,
                  fontWeight: 800,
                }}
              >
                {item}
              </div>
            ))}
          </div>
        </div>

        <div style={{ marginTop: 28, borderRadius: 8, border: "1px solid #d9e2ec", overflow: "hidden" }}>
          <div style={{ padding: "22px 28px", background: "#f8fafc" }}>
            <div style={{ color: colors.blue, fontSize: 28, fontWeight: 900, marginBottom: 14 }}>描述</div>
            <div style={{ fontSize: 28, lineHeight: 1.55 }}>{lessonData.problem.description}</div>
            <div style={{ marginTop: 14, fontSize: 28, lineHeight: 1.55 }}>要求：</div>
            {lessonData.problem.requirements.map((item, index) => (
              <div key={item} style={{ marginLeft: 28, fontSize: 26, lineHeight: 1.55 }}>
                ({index + 1}) {item}
              </div>
            ))}
          </div>
          <div style={{ padding: "22px 28px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
              <div>
                <div style={{ color: colors.blue, fontSize: 26, fontWeight: 900, marginBottom: 12 }}>输入描述</div>
                <div style={{ fontSize: 25 }}>输入多行密码</div>
              </div>
              <div>
                <div style={{ color: colors.blue, fontSize: 26, fontWeight: 900, marginBottom: 12 }}>输出描述</div>
                <div style={{ fontSize: 25 }}>直到密码正确，输出：“密码正确，欢迎您！”</div>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22, marginTop: 28 }}>
              <div>
                <div style={{ color: colors.blue, fontSize: 26, fontWeight: 900, marginBottom: 12 }}>样例输入 1</div>
                <CodeBox fontSize={27}>{lessonData.problem.sampleInput.join("\n")}</CodeBox>
              </div>
              <div>
                <div style={{ color: colors.blue, fontSize: 26, fontWeight: 900, marginBottom: 12 }}>样例输出 1</div>
                <CodeBox fontSize={27}>{lessonData.problem.sampleOutput.join("\n")}</CodeBox>
              </div>
            </div>
          </div>
          <div style={{ padding: "18px 28px", background: colors.softAmber, borderTop: "1px solid #fed7aa" }}>
            <div style={{ color: "#9a3412", fontSize: 24, fontWeight: 850 }}>提示：{lessonData.problem.hint}</div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}

function IntroScene() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={shell}>
      <Audio src={staticFile(voiceover.intro.audio)} />
      <Header active={0} />
      <Panel x={44} w={910} title="题目要求" accent={colors.blue}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {lessonData.intro.ruleCards.map((item, index) => (
            <div
              key={item.title}
              style={{
                ...fade(frame, 10 + index * 16),
                minHeight: 150,
                borderRadius: 8,
                background: index === 3 ? colors.softRed : "#fff",
                border: `1px solid ${index === 3 ? "#fecaca" : colors.border}`,
                padding: "20px",
                boxSizing: "border-box",
              }}
            >
              <div style={{ color: index === 3 ? colors.red : colors.blue, fontSize: 27, fontWeight: 850, marginBottom: 12 }}>
                {item.title}
              </div>
              <div style={{ fontSize: 26, lineHeight: 1.42 }}>{item.text}</div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 22, borderRadius: 8, background: colors.softAmber, border: "1px solid #fed7aa", padding: 20 }}>
          <div style={{ color: "#9a3412", fontSize: 24, fontWeight: 800, marginBottom: 8 }}>关键输出规则</div>
          <div style={{ fontSize: 32, fontWeight: 900 }}>错误时不输出，正确时输出并退出。</div>
        </div>
      </Panel>
      <Panel x={1000} w={876} title="输入与输出" accent={colors.green}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginBottom: 20 }}>
          <div style={{ border: "1px solid #bbf7d0", background: colors.softGreen, borderRadius: 8, padding: 18 }}>
            <div style={{ color: colors.green, fontSize: 24, fontWeight: 800, marginBottom: 10 }}>输入</div>
            {lessonData.intro.inputLines.map((line) => (
              <div key={line} style={{ fontSize: 27, lineHeight: 1.55 }}>
                {line}
              </div>
            ))}
          </div>
          <div style={{ border: "1px solid #bfdbfe", background: colors.softBlue, borderRadius: 8, padding: 18 }}>
            <div style={{ color: colors.blue, fontSize: 24, fontWeight: 800, marginBottom: 10 }}>输出</div>
            {lessonData.intro.outputLines.map((line) => (
              <div key={line} style={{ fontSize: 27, lineHeight: 1.55 }}>
                {line}
              </div>
            ))}
          </div>
        </div>
        <div style={{ borderRadius: 8, border: "1px solid #ddd6fe", background: colors.softViolet, padding: 20 }}>
          <div style={{ color: colors.violet, fontSize: 24, fontWeight: 800, marginBottom: 12 }}>考点标签</div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            {lessonData.intro.tags.map((tag) => (
              <div
                key={tag}
                style={{
                  height: 48,
                  borderRadius: 8,
                  padding: "0 16px",
                  background: "#fff",
                  border: "1px solid #c4b5fd",
                  display: "flex",
                  alignItems: "center",
                  color: colors.violet,
                  fontSize: 25,
                  fontWeight: 850,
                }}
              >
                {tag}
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 24 }}>
          <CodeBox>
            {'password = "123456"\nif s == password:\n    print("密码正确，欢迎您！")\n    break'}
          </CodeBox>
        </div>
      </Panel>
    </AbsoluteFill>
  );
}

function SampleScene() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={shell}>
      <Audio src={staticFile(voiceover.sample.audio)} />
      <Header active={1} />
      <Panel x={44} w={570} title="样例输入输出" accent={colors.blue}>
        <div style={{ color: colors.muted, fontSize: 22, fontWeight: 800, marginBottom: 8 }}>正确密码</div>
        <CodeBox fontSize={36}>{lessonData.sample.password}</CodeBox>
        <div style={{ marginTop: 16, color: colors.muted, fontSize: 22, fontWeight: 800, marginBottom: 8 }}>样例输入</div>
        <CodeBox fontSize={32}>{lessonData.sample.input.join("\n")}</CodeBox>
        <div style={{ marginTop: 16, borderRadius: 8, background: colors.softBlue, border: "1px solid #bfdbfe", padding: 14 }}>
          <div style={{ color: colors.blue, fontSize: 23, fontWeight: 850, marginBottom: 6 }}>样例输出</div>
          <div style={{ fontFamily: codeFont, fontSize: 27, fontWeight: 900 }}>{lessonData.sample.output.join("\n")}</div>
        </div>
      </Panel>
      <Panel x={660} w={1216} title="逐次比较" accent={colors.green}>
        <div style={{ display: "grid", gap: 12 }}>
          {lessonData.sample.rows.map((row, index) => {
            const p = spring({
              frame: Math.max(0, frame - index * 24),
              fps,
              config: { damping: 18, mass: 0.8 },
            });
            const ok = row.status === "正确";
            return (
              <div
                key={row.value}
                style={{
                  opacity: p,
                  transform: `translateY(${(1 - p) * 18}px)`,
                  borderRadius: 8,
                  border: `2px solid ${ok ? "#bbf7d0" : "#e5e7eb"}`,
                  background: ok ? colors.softGreen : "#fff",
                  padding: "13px 16px",
                  display: "grid",
                  gridTemplateColumns: "130px 260px 120px 180px 1fr",
                  alignItems: "center",
                  gap: 14,
                }}
              >
                <div style={{ fontFamily: codeFont, fontSize: 30, fontWeight: 900 }}>{row.value}</div>
                <div style={{ fontFamily: codeFont, fontSize: 25 }}>{row.compare}</div>
                <div style={{ color: ok ? colors.green : colors.red, fontSize: 25, fontWeight: 900 }}>{row.status}</div>
                <div style={{ fontSize: 25, fontWeight: 800 }}>{row.action}</div>
                <div style={{ fontSize: ok ? 25 : 23, fontWeight: 900, color: ok ? colors.blue : colors.muted }}>{row.result}</div>
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 20, borderRadius: 8, border: "1px solid #fed7aa", background: colors.softAmber, padding: "18px 20px", fontSize: 27, fontWeight: 850, color: "#9a3412" }}>
          样例输出只有一行，因为前五次错误输入都不产生输出。
        </div>
      </Panel>
    </AbsoluteFill>
  );
}

function StrategyScene() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={shell}>
      <Audio src={staticFile(voiceover.strategy.audio)} />
      <Header active={2} />
      <Panel x={44} w={770} title="程序步骤" accent={colors.blue}>
        <div style={{ display: "grid", gap: 15 }}>
          {lessonData.strategy.tasks.map((task, index) => (
            <div
              key={task}
              style={{
                ...fade(frame, index * 12),
                borderRadius: 8,
                border: "1px solid #d9e2ec",
                background: index === 2 ? colors.softAmber : index % 2 === 0 ? "#fff" : "#f8fafc",
                minHeight: 72,
                display: "flex",
                alignItems: "center",
                padding: "0 20px",
                fontSize: 26,
                fontWeight: 800,
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 8,
                  background: index === 2 ? colors.amber : colors.blue,
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: 18,
                  fontWeight: 900,
                }}
              >
                {index + 1}
              </div>
              {task}
            </div>
          ))}
        </div>
      </Panel>
      <Panel x={858} w={1018} title="伪代码" accent={colors.violet}>
        <CodeBox fontSize={34}>
          {lessonData.strategy.pseudoLines.map((line, index) => (
            <div key={`${index}-${line}`} style={fade(frame, 8 + index * 7)}>
              {line}
            </div>
          ))}
        </CodeBox>
        <div style={{ marginTop: 26, borderRadius: 8, background: colors.softAmber, border: "1px solid #fed7aa", padding: 22 }}>
          <div style={{ color: "#9a3412", fontSize: 25, fontWeight: 850, marginBottom: 8 }}>不要多输出</div>
          <div style={{ fontSize: 29, lineHeight: 1.42 }}>{lessonData.strategy.warning}</div>
        </div>
      </Panel>
    </AbsoluteFill>
  );
}

function TraceScene() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={shell}>
      <Audio src={staticFile(voiceover.trace.audio)} />
      <Header active={3} />
      <Panel x={44} w={1832} title="循环变量追踪" accent={colors.green}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", background: colors.green, color: "#fff", borderRadius: "8px 8px 0 0", overflow: "hidden" }}>
          {lessonData.trace.columns.map((column) => (
            <div key={column} style={{ padding: "16px 18px", fontSize: 26, fontWeight: 900 }}>
              {column}
            </div>
          ))}
        </div>
        <div style={{ border: "1px solid #bbf7d0", borderTop: "none", borderRadius: "0 0 8px 8px", overflow: "hidden" }}>
          {lessonData.trace.rows.map((row, index) => {
            const p = interpolate(frame, [index * 18, index * 18 + 12], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const ok = row[2] === "True";
            return (
              <div
                key={row.join("-")}
                style={{
                  opacity: p,
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  background: ok ? colors.softGreen : index % 2 === 0 ? "#fff" : "#f8fafc",
                  borderTop: index === 0 ? "none" : "1px solid #e5e7eb",
                }}
              >
                {row.map((cell, cellIndex) => (
                  <div
                    key={`${cellIndex}-${cell}`}
                    style={{
                      padding: "16px 18px",
                      fontFamily: cellIndex === 1 || cellIndex === 2 ? codeFont : undefined,
                      fontSize: 29,
                      fontWeight: ok || cellIndex === 2 ? 850 : 600,
                      color: ok ? colors.green : cellIndex === 2 ? colors.red : colors.ink,
                    }}
                  >
                    {cell}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 28, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
          <div style={{ borderRadius: 8, background: colors.softBlue, border: "1px solid #bfdbfe", padding: 24 }}>
            <div style={{ color: colors.blue, fontSize: 27, fontWeight: 900, marginBottom: 10 }}>比较表达式</div>
            <div style={{ fontFamily: codeFont, fontSize: 48, fontWeight: 900 }}>{lessonData.trace.formula}</div>
          </div>
          <div style={{ borderRadius: 8, background: colors.softRed, border: "1px solid #fecaca", padding: 24 }}>
            <div style={{ color: colors.red, fontSize: 27, fontWeight: 900, marginBottom: 10 }}>错误时</div>
            <div style={{ fontSize: 38, fontWeight: 900 }}>不输出，不 break，继续下一轮。</div>
          </div>
        </div>
      </Panel>
    </AbsoluteFill>
  );
}

function CodeBlock({ lines, highlight, frame }: { lines: readonly string[]; highlight: readonly number[]; frame: number }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #d9e2ec",
        borderRadius: 8,
        padding: "22px 24px",
        boxSizing: "border-box",
        height: "100%",
        overflow: "hidden",
      }}
    >
      <div style={{ fontFamily: codeFont, fontSize: 40, lineHeight: 1.52 }}>
        {lines.map((line, index) => {
          const no = index + 1;
          const active = highlight.includes(no);
          const appear = interpolate(frame, [index * 8, index * 8 + 12], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={`${no}-${line}`}
              style={{
                opacity: appear,
                display: "flex",
                gap: 16,
                background: active ? "#dbeafe" : "transparent",
                borderRadius: 6,
                padding: "0 9px",
              }}
            >
              <div style={{ width: 42, textAlign: "right", color: active ? colors.blue : "#94a3b8" }}>{no}</div>
              <div style={{ whiteSpace: "pre-wrap", color: "#1f2937" }}>{line || " "}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function CodeScene() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={shell}>
      <Audio src={staticFile(voiceover.code.audio)} />
      <Header active={4} />
      <Panel x={44} w={600} title="代码对应思路" accent={colors.blue}>
        <div style={{ display: "grid", gap: 16 }}>
          {lessonData.code.callouts.map((callout, index) => (
            <div
              key={callout.title}
              style={{
                ...fade(frame, index * 17),
                borderRadius: 8,
                border: "1px solid #d9e2ec",
                background: index === 2 ? colors.softAmber : "#fff",
                padding: "18px 20px",
              }}
            >
              <div style={{ fontSize: 25, fontWeight: 900, color: index === 2 ? "#9a3412" : colors.blue, marginBottom: 8 }}>
                {callout.title}
              </div>
              <div style={{ fontSize: 23, lineHeight: 1.45 }}>{callout.text}</div>
            </div>
          ))}
        </div>
      </Panel>
      <div style={{ position: "absolute", left: 690, top: 142, width: 1186, height: 792 }}>
        <CodeBlock lines={lessonData.code.lines} highlight={lessonData.code.highlight} frame={frame} />
      </div>
    </AbsoluteFill>
  );
}

function SummaryScene() {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={shell}>
      <Audio src={staticFile(voiceover.summary.audio)} />
      <Header active={5} />
      <Panel x={44} w={910} title="最后记住这条链路" accent={colors.green}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginTop: 18 }}>
          {lessonData.summary.chain.map((item, index) => (
            <React.Fragment key={item}>
              <div
                style={{
                  ...fade(frame, index * 16),
                  height: 72,
                  borderRadius: 8,
                  padding: "0 18px",
                  background: colors.softGreen,
                  border: "1px solid #bbf7d0",
                  color: colors.green,
                  display: "flex",
                  alignItems: "center",
                  fontSize: 26,
                  fontWeight: 900,
                }}
              >
                {item}
              </div>
              {index < lessonData.summary.chain.length - 1 ? <div style={{ fontSize: 34, color: "#94a3b8" }}>→</div> : null}
            </React.Fragment>
          ))}
        </div>
        <div style={{ marginTop: 38, borderRadius: 8, background: colors.softBlue, border: "1px solid #bfdbfe", padding: 24 }}>
          <div style={{ color: colors.blue, fontSize: 30, fontWeight: 900 }}>只有正确时进入 if</div>
          <div style={{ marginTop: 10, fontFamily: codeFont, fontSize: 42, fontWeight: 900 }}>{lessonData.summary.keyCode}</div>
        </div>
      </Panel>
      <Panel x={998} w={878} title="容易错的地方" accent={colors.red}>
        <div style={{ display: "grid", gap: 16 }}>
          {lessonData.summary.mistakes.map((mistake, index) => (
            <div
              key={mistake}
              style={{
                ...fade(frame, index * 17),
                minHeight: 82,
                borderRadius: 8,
                border: "1px solid #fecaca",
                background: index === 0 ? colors.softRed : "#fff",
                padding: "0 20px",
                display: "flex",
                alignItems: "center",
                fontSize: 25,
                lineHeight: 1.35,
              }}
            >
              <div
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 8,
                  background: colors.red,
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: 16,
                  fontWeight: 900,
                }}
              >
                {index + 1}
              </div>
              {mistake}
            </div>
          ))}
        </div>
      </Panel>
    </AbsoluteFill>
  );
}

export const PasswordJudgementLesson: React.FC = () => {
  return (
    <>
      <Sequence from={sceneStarts.problem} durationInFrames={sceneDurations.problem}>
        <ProblemScene />
      </Sequence>
      <Sequence from={sceneStarts.intro} durationInFrames={sceneDurations.intro}>
        <IntroScene />
      </Sequence>
      <Sequence from={sceneStarts.sample} durationInFrames={sceneDurations.sample}>
        <SampleScene />
      </Sequence>
      <Sequence from={sceneStarts.strategy} durationInFrames={sceneDurations.strategy}>
        <StrategyScene />
      </Sequence>
      <Sequence from={sceneStarts.trace} durationInFrames={sceneDurations.trace}>
        <TraceScene />
      </Sequence>
      <Sequence from={sceneStarts.code} durationInFrames={sceneDurations.code}>
        <CodeScene />
      </Sequence>
      <Sequence from={sceneStarts.summary} durationInFrames={sceneDurations.summary}>
        <SummaryScene />
      </Sequence>
    </>
  );
};
