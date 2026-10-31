(function (factory) {
  const api = factory();
  if (typeof window === "object") {
    window.FeedbackBuilder = api;
  }
  if (typeof globalThis === "object") {
    globalThis.FeedbackBuilder = api;
  }
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
})(function () {
  function text(value) {
    return String(value || "").trim();
  }

  function parseStudentJson(payload) {
    const records = Array.isArray(payload) ? payload : payload && payload.students;
    if (!Array.isArray(records)) {
      throw new Error("JSON 需要是学生数组，或包含 students 数组。");
    }
    return records
      .map((record, index) => {
        const displayName =
          text(record.real_name) ||
          text(record.realName) ||
          text(record.name) ||
          text(record.nickname) ||
          text(record.username) ||
          `学生${index + 1}`;
        return {
          uid: text(record.uid) || text(record.id) || text(record.username) || String(index + 1),
          displayName,
          username: text(record.username),
        };
      })
      .filter((student) => student.displayName);
  }

  function pointList(value) {
    return text(value)
      .split(/[、,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function compressKnowledgePoints(value) {
    const source = text(value);
    if (!source) return "";
    const normalized = source
      .replace(/本节课|主要|学习了|学习|课堂中|反复|练习了|练习|如何|为什么|以及|时|的含义|含义|判断|注意|要/g, "")
      .replace(/[。；;.!！?？]/g, "\n")
      .replace(/[ \t]+/g, "");
    const rawPoints = normalized
      .split(/[、,，\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
    const points = [];
    rawPoints.forEach((point) => {
      const cleaned = point
        .replace(/^了+/, "")
        .replace(/^还+/, "")
        .replace(/了+$/, "")
        .replace(/怎么/g, "")
        .replace(/和/g, "、");
      cleaned
        .split(/、/)
        .map((item) => item.trim())
        .filter(Boolean)
        .forEach((item) => {
          if (!points.includes(item)) points.push(item);
        });
    });
    return points.slice(0, 6).join("、");
  }

  function findPastedImageFile(event) {
    const clipboardData = event && event.clipboardData;
    if (!clipboardData) return null;
    const files = Array.from(clipboardData.files || []);
    const fileMatch = files.find((file) => /^image\//.test(text(file && file.type)));
    if (fileMatch) return fileMatch;
    const items = Array.from(clipboardData.items || []);
    const imageItem = items.find((item) => /^image\//.test(text(item && item.type)));
    if (imageItem && typeof imageItem.getAsFile === "function") {
      return imageItem.getAsFile();
    }
    return null;
  }

  function buildKnowledgeSentence(topic, points) {
    const topicText = text(topic) || "本节课内容";
    if (!points.length) {
      return `本节课我们围绕${topicText}进行了学习，主要目标是先把课堂核心思路整理清楚。`;
    }
    return `本节课我们围绕${topicText}进行了学习，重点接触了${points.join("、")}等内容。`;
  }

  function dimensionText(value, fallback = "") {
    const result = text(value);
    return result || fallback;
  }

  function levelSentence(level) {
    return {
      优秀:
        "整体看，孩子对课堂主线吸收较快，能够顺着讲解把知识点和题目要求对应起来，后续可以多做一点综合题来提高迁移熟练度。",
      优生版:
        "整体看，孩子对课堂主线吸收较快，能够顺着讲解把知识点和题目要求对应起来，后续可以多做一点综合题来提高迁移熟练度。",
      中等:
        "整体看，孩子能跟上课堂主要内容，对核心概念有初步理解，后续需要继续通过同类练习把细节和步骤稳定下来。",
      中等版:
        "整体看，孩子能跟上课堂主要内容，对核心概念有初步理解，后续需要继续通过同类练习把细节和步骤稳定下来。",
      差:
        "整体看，孩子已经接触到本节课的主要内容，后续建议把知识点拆小复习，再配合基础题逐步熟悉解题步骤。",
      薄弱版:
        "整体看，孩子已经接触到本节课的主要内容，后续建议把知识点拆小复习，再配合基础题逐步熟悉解题步骤。",
      压缩版:
        "课后建议围绕本节课重点做 2-3 道同类题，把概念、步骤和易错细节再过一遍。",
    }[level] || "整体看，孩子能跟着课堂推进，后续可以继续巩固本节课的重点内容。";
  }

  function dimensionSentence(dimensions) {
    if (!dimensions) return "";
    const understanding = dimensionText(dimensions.understanding);
    const independence = dimensionText(dimensions.independence);
    const classroomState = dimensionText(dimensions.classroomState);
    const mainIssue = dimensionText(dimensions.mainIssue);
    const parts = [];

    if (understanding === "理解清楚") {
      parts.push("对课堂核心概念理解比较清楚");
    } else if (understanding === "初步理解") {
      parts.push("对核心概念有初步理解");
    } else if (understanding === "还需熟悉") {
      parts.push("已经接触到本节课核心概念，后续还需要继续熟悉");
    }

    if (independence === "基本独立") {
      parts.push("大部分关键步骤可以自己完成");
    } else if (independence === "提示后完成") {
      parts.push("在提示后能继续完成主要步骤");
    } else if (independence === "分步引导") {
      parts.push("需要按步骤引导来慢慢推进");
    }

    if (classroomState === "很投入") {
      parts.push("课堂投入度比较好");
    } else if (classroomState === "比较稳定") {
      parts.push("课堂状态比较稳定");
    } else if (classroomState === "需要提醒") {
      parts.push("课堂过程中偶尔需要提醒后再继续跟进");
    }

    if (mainIssue) {
      parts.push(`当前可以重点关注${mainIssue}这类细节`);
    }

    return parts.join("，");
  }

  function buildAfterClassFeedback(student, options) {
    const topic = text(options && options.topic);
    const points = pointList(options && options.knowledgePoints);
    const level = text(options && options.level) || "中等";
    const dimensions = options && options.dimensions;
    const reviewFocus = points.length ? points.slice(0, 3).join("、") : "课堂重点";
    const detail = dimensionSentence(dimensions);

    return [
      `#沟通称呼语#～${buildKnowledgeSentence(topic, points)}`,
      `#学员昵称#同学这节课主要是跟着课堂节奏梳理知识点和题目思路。${detail ? `${detail}。` : ""}${levelSentence(level)}`,
      `课后可以重点复习${reviewFocus}，再做几道同类型练习，帮助孩子把课堂内容真正用熟～`,
    ].join("\n\n");
  }

  function buildFeedbackList(students, options) {
    return students.map((student, index) => {
      const studentOptions = typeof options === "function" ? options(student, index) : options;
      return {
        student,
        feedback: buildAfterClassFeedback(student, studentOptions),
      };
    });
  }

  return {
    buildAfterClassFeedback,
    buildFeedbackList,
    compressKnowledgePoints,
    findPastedImageFile,
    parseStudentJson,
  };
});
