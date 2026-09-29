// Usage: node oracle.mjs <cases.json>   -> prints one JSON result per case, as a JSON array.
// cases.json: {"contexts": {name: json}, "cases": [{"expr": str, "ctx": name, "status": str}]}
import fs from "node:fs";
import { Lexer, Parser, Evaluator, data } from "@actions/expressions";
import { reviver } from "@actions/expressions/data/reviver";
import { kindStr } from "@actions/expressions/data/expressiondata";

const input = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const contexts = {};
for (const [name, value] of Object.entries(input.contexts)) {
  contexts[name] = JSON.parse(JSON.stringify(value), reviver);
}

function num(v) {
  return Object.is(v, -0) ? "-0" : String(v);
}

function enc(d) {
  switch (kindStr(d.kind)) {
    case "Null":
      return { k: "Null" };
    case "Boolean":
      return { k: "Boolean", v: d.value };
    case "Number":
      return { k: "Number", v: num(d.value) };
    case "String":
      return { k: "String", v: d.value };
    case "Array":
      return { k: "Array", v: d.values().map(enc) };
    case "Object":
      return { k: "Object", v: d.pairs().map(p => [p.key, enc(p.value)]) };
  }
  return { k: "?" };
}

const fnInfo = [
  { name: "hashFiles", minArgs: 1, maxArgs: 255 },
  { name: "success", minArgs: 0, maxArgs: 0 },
  { name: "failure", minArgs: 0, maxArgs: 0 },
  { name: "always", minArgs: 0, maxArgs: 0 },
  { name: "cancelled", minArgs: 0, maxArgs: 0 },
];

function functionsFor(status) {
  const m = new Map();
  m.set("hashfiles", {
    ...fnInfo[0],
    call: (...args) => new data.StringData("hash:" + args.map(a => a.coerceString()).join("|")),
  });
  m.set("success", { ...fnInfo[1], call: () => new data.BooleanData(status === "success") });
  m.set("failure", { ...fnInfo[2], call: () => new data.BooleanData(status === "failure") });
  m.set("always", { ...fnInfo[3], call: () => new data.BooleanData(true) });
  m.set("cancelled", { ...fnInfo[4], call: () => new data.BooleanData(status === "cancelled") });
  return m;
}

const out = [];
for (const c of input.cases) {
  const ctx = contexts[c.ctx];
  let phase = "lexing";
  try {
    const lexed = new Lexer(c.expr).lex();
    phase = "parsing";
    const names = ctx.pairs().map(p => p.key);
    const tree = new Parser(lexed.tokens, names, fnInfo).parse();
    phase = "evaluation";
    let result;
    if (tree === undefined) {
      result = new data.Null();
    } else {
      result = new Evaluator(tree, ctx, functionsFor(c.status ?? "success")).evaluate();
    }
    out.push({ ok: enc(result) });
  } catch (e) {
    let msg = e.message;
    if (phase === "parsing" && e.pos !== undefined) {
      msg = `${e.message}. Located at position ${e.pos.column + 1} within expression: ${c.expr}`;
    }
    out.push({ err: { kind: phase, msg } });
  }
}
process.stdout.write(JSON.stringify(out));
