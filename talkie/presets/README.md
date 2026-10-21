# 克讲机的「常用功能」放在这里 / Presets

一个 .md 文件 = 一个常用功能，对讲机的「常用」旋钮里会列出来（按文件名排序，开头的数字只管顺序）。
在对讲机里也能改、能删、能新建（「常用」旋钮 → 改 / 新建；删掉的放进 `deleted/`，能找回）。

写法：
- 第一行 `# 名字`（旋钮里显示的名字）
- 可选第二行 `来自：<文件路径>｜<段落名>`：从别的文件里读一段规矩（那个文件里要有 `<!-- 克讲机:段落名 开始 -->` 和 `<!-- 克讲机:段落名 结束 -->` 两行标记）。规矩只写一份，主对话和克讲机都用它
- 剩下的就是这个功能自己的规矩，会加在模型的说明后面

这个 README.md 不会出现在旋钮里。

---

One `.md` file = one preset, listed under the "常用" (presets) knob (sorted by file name; the leading number only sets the order).
Line 1 `# name`; optional line 2 `来自：<path>｜<section>` pulls a section marked `<!-- 克讲机:<section> 开始 -->` … `<!-- 克讲机:<section> 结束 -->` from another file; the rest is the rule text appended to the model's instructions.
