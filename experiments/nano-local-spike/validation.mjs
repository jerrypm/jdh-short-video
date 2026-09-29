export const ideaSchema = {
  type: "object",
  properties: {
    ideas: {
      type: "array", minItems: 3, maxItems: 3,
      items: {
        type: "object",
        properties: {
          title: { type: "string", minLength: 1, maxLength: 120 },
          hook: { type: "string", minLength: 1, maxLength: 240 },
        },
        required: ["title", "hook"], additionalProperties: false,
      },
    },
  },
  required: ["ideas"], additionalProperties: false,
};

export function validateIdeas(text) {
  const value = JSON.parse(text);
  if (!value || Array.isArray(value) || Object.keys(value).join() !== "ideas" ||
      !Array.isArray(value.ideas) || value.ideas.length !== 3) {
    throw new Error("Expected exactly three ideas and no extra fields.");
  }
  const titles = new Set();
  for (const idea of value.ideas) {
    if (!idea || typeof idea !== "object" || Array.isArray(idea) ||
        Object.keys(idea).sort().join() !== "hook,title") {
      throw new Error("Each idea must contain only title and hook.");
    }
    for (const [key, limit] of [["title", 120], ["hook", 240]]) {
      if (typeof idea[key] !== "string" || !idea[key].trim() || idea[key].length > limit) {
        throw new Error("Invalid " + key + ".");
      }
    }
    const key = idea.title.trim().toLowerCase();
    if (titles.has(key)) throw new Error("Repeated idea title.");
    titles.add(key);
  }
  return value;
}
