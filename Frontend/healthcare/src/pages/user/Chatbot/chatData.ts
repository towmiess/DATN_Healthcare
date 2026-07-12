export interface WelcomeTopic {
  icon: string;
  label: string;
  questions: string[];
}

export const WELCOME_TOPICS: WelcomeTopic[] = [
  {
    icon: "🩺",
    label: "Chẩn đoán & Xét nghiệm",
    questions: ["HbA1c bao nhiêu là cần điều trị?", "Tiểu đường có thể chẩn đoán tại nhà không?"],
  },
  {
    icon: "🍚",
    label: "Chế độ ăn uống",
    questions: ["Người tiểu đường type 2 ăn phở được không?", "Thực đơn 1 ngày cho người tiểu đường?"],
  },
  {
    icon: "💊",
    label: "Thuốc & Điều trị",
    questions: ["Metformin uống lúc nào tốt nhất?", "Khi nào cần chuyển sang dùng insulin?"],
  },
  {
    icon: "⚠️",
    label: "Biến chứng",
    questions: ["Biến chứng tim mạch của tiểu đường?", "Tiểu đường có ảnh hưởng đến thận không?"],
  },
  {
    icon: "🏃",
    label: "Lối sống & Phòng ngừa",
    questions: ["Người tiểu đường nên tập thể dục gì?", "Làm sao phòng ngừa tiền tiểu đường?"],
  },
  {
    icon: "🚨",
    label: "Xử lý khẩn cấp",
    questions: ["Hạ đường huyết phải làm gì?", "Dấu hiệu tăng đường huyết nguy hiểm?"],
  },
];

export const EXAMPLE_QUESTIONS: string[] = [
  "HbA1c bao nhiêu là cần điều trị?",
  "Metformin uống lúc nào tốt nhất?",
  "Tiểu đường có ảnh hưởng đến thận không?",
  "Hạ đường huyết phải làm gì?",
  "Phân biệt tiểu đường type 1, type 2 và thai kỳ",
  "Biến chứng tim mạch của tiểu đường?",
];

const TOPIC_FOLLOWUPS: Record<string, string[]> = {
  "chẩn đoán": [
    "HbA1c bao nhiêu là bị tiểu đường?",
    "Xét nghiệm đường huyết lúc đói bình thường là bao nhiêu?",
    "Tiền tiểu đường có cần điều trị không?",
  ],
  "chế độ ăn": [
    "Người tiểu đường nên ăn bao nhiêu tinh bột mỗi ngày?",
    "Trái cây nào người tiểu đường ăn được?",
    "Chỉ số GI (glycemic index) là gì?",
  ],
  thuốc: [
    "Metformin có tác dụng phụ gì không?",
    "Khi nào cần dùng insulin?",
    "Thuốc tiểu đường uống lúc nào là tốt nhất?",
  ],
  "biến chứng": [
    "Tiểu đường ảnh hưởng đến thận như thế nào?",
    "Biến chứng mắt của tiểu đường có chữa được không?",
    "Bệnh thần kinh ngoại biên do tiểu đường là gì?",
  ],
  "hạ đường huyết": [
    "Triệu chứng hạ đường huyết là gì?",
    "Khi hạ đường huyết nên ăn gì để tăng nhanh?",
    "Làm sao phòng ngừa hạ đường huyết ban đêm?",
  ],
  "lối sống": [
    "Người tiểu đường nên tập thể dục như thế nào?",
    "Stress ảnh hưởng đến đường huyết không?",
    "Người tiểu đường có uống rượu bia được không?",
  ],
  "mặc định": [
    "Tiểu đường type 1 khác type 2 như thế nào?",
    "Khi nào cần đi khám tiểu đường ngay?",
    "Tự theo dõi đường huyết tại nhà như thế nào?",
  ],
};

export const getFollowups = (question: string): string[] => {
  const q = question.toLowerCase();
  const has = (words: string[]) => words.some((w) => q.includes(w));

  if (has(["hba1c", "xét nghiệm", "chẩn đoán", "đường huyết", "glucose"])) {
    return TOPIC_FOLLOWUPS["chẩn đoán"];
  }
  if (has(["ăn", "thực phẩm", "diet", "phở", "cơm", "trái cây", "đường"])) {
    return TOPIC_FOLLOWUPS["chế độ ăn"];
  }
  if (has(["thuốc", "metformin", "insulin", "uống", "tiêm"])) {
    return TOPIC_FOLLOWUPS["thuốc"];
  }
  if (has(["biến chứng", "thận", "mắt", "tim", "thần kinh", "võng mạc"])) {
    return TOPIC_FOLLOWUPS["biến chứng"];
  }
  if (has(["hạ đường", "hypoglycemia", "chóng mặt", "run"])) {
    return TOPIC_FOLLOWUPS["hạ đường huyết"];
  }
  if (has(["tập", "thể dục", "vận động", "stress", "rượu", "bia", "ngủ"])) {
    return TOPIC_FOLLOWUPS["lối sống"];
  }
  return TOPIC_FOLLOWUPS["mặc định"];
};

type FollowupRule = {
  keywords: string[];
  questions: string[];
};

const CONTEXTUAL_FOLLOWUP_RULES: FollowupRule[] = [
  {
    keywords: ["type 1", "tuýp 1", "typ 1", "type 2", "tuýp 2", "typ 2", "kháng insulin", "tự miễn"],
    questions: [
      "Dấu hiệu nào giúp phân biệt tiểu đường type 1 và type 2?",
      "Người tiểu đường type 2 khi nào cần dùng insulin?",
      "Tiểu đường type 1 có phòng ngừa được không?",
    ],
  },
  {
    keywords: ["thai kỳ", "mang thai", "thai phụ", "sau sinh"],
    questions: [
      "Tiểu đường thai kỳ cần theo dõi đường huyết như thế nào?",
      "Sau sinh bao lâu cần kiểm tra lại tiểu đường thai kỳ?",
      "Thai phụ bị tiểu đường nên ăn uống ra sao?",
    ],
  },
  {
    keywords: ["hba1c", "xét nghiệm", "chẩn đoán", "glucose", "đường huyết lúc đói"],
    questions: [
      "HbA1c bao nhiêu là kiểm soát tốt?",
      "Nên xét nghiệm HbA1c bao lâu một lần?",
      "Đường huyết lúc đói và HbA1c khác nhau như thế nào?",
    ],
  },
  {
    keywords: ["gi", "glycemic", "carbohydrate", "carb", "tinh bột", "thực phẩm", "dinh dưỡng", "khẩu phần", "bảng"],
    questions: [
      "Người tiểu đường nên ăn bao nhiêu tinh bột mỗi bữa?",
      "Chỉ số GI và GL khác nhau như thế nào?",
      "Có thể lập thực đơn 1 ngày theo bảng dinh dưỡng này không?",
    ],
  },
  {
    keywords: ["insulin", "tiêm", "metformin", "thuốc", "liều", "uống thuốc"],
    questions: [
      "Khi nào người tiểu đường type 2 cần chuyển sang insulin?",
      "Dùng insulin cần lưu ý nguy cơ hạ đường huyết thế nào?",
      "Metformin có thể dùng chung với insulin không?",
    ],
  },
  {
    keywords: ["hạ đường huyết", "hypoglycemia", "run", "vã mồ hôi", "chóng mặt", "mệt", "lơ mơ"],
    questions: [
      "Hạ đường huyết bao nhiêu là nguy hiểm?",
      "Quy tắc 15-15 khi hạ đường huyết là gì?",
      "Làm sao phòng ngừa hạ đường huyết ban đêm?",
    ],
  },
  {
    keywords: ["biến chứng", "tim mạch", "thận", "mắt", "võng mạc", "bàn chân", "thần kinh"],
    questions: [
      "Người tiểu đường cần tầm soát biến chứng nào hằng năm?",
      "Dấu hiệu biến chứng bàn chân tiểu đường là gì?",
      "Làm sao giảm nguy cơ biến chứng thận do tiểu đường?",
    ],
  },
  {
    keywords: ["tập", "thể dục", "vận động", "giảm cân", "stress", "giấc ngủ", "rượu", "bia"],
    questions: [
      "Người tiểu đường nên tập thể dục vào thời điểm nào?",
      "Tập luyện ảnh hưởng đến đường huyết ra sao?",
      "Stress và thiếu ngủ làm tăng đường huyết như thế nào?",
    ],
  },
];

const normalizeFollowupText = (text: string): string =>
  text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d");

const uniqueFollowupQuestions = (questions: string[], currentQuestion: string): string[] => {
  const current = normalizeFollowupText(currentQuestion);
  const seen = new Set<string>();

  return questions.filter((question) => {
    const normalized = normalizeFollowupText(question);
    if (!normalized || normalized === current || seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
};

export const getContextualFollowups = (question: string, answer = ""): string[] => {
  const context = normalizeFollowupText(`${question}\n${answer}`);
  const fallback = getFollowups(question);
  const scoredRules = CONTEXTUAL_FOLLOWUP_RULES.map((rule) => {
    const score = rule.keywords.reduce((total, keyword) => {
      return context.includes(normalizeFollowupText(keyword)) ? total + 1 : total;
    }, 0);
    return { ...rule, score };
  })
    .filter((rule) => rule.score > 0)
    .sort((a, b) => b.score - a.score);

  const contextualQuestions = scoredRules.flatMap((rule) => rule.questions);
  return uniqueFollowupQuestions([...contextualQuestions, ...fallback], question).slice(0, 3);
};

const TEACH_PREFIXES = [
  "/nho ",
  "nhớ rằng ",
  "ghi nhớ rằng ",
  "lưu ý rằng ",
  "thông tin của tôi là ",
  "tri thức mới: ",
];

export const detectTeachIntent = (prompt: string): boolean => {
  const lowered = prompt.toLowerCase();
  return TEACH_PREFIXES.some((prefix) => lowered.startsWith(prefix));
};

export const ROUTE_ICON: Record<string, string> = {
  drug: "💊",
  document: "📃",
  emergency: "🚨",
};
