/* lanshu_beats.js — C 迴圈邊界手帳演示 */
window.Beats = function (api) {
  'use strict';
  const story = api.story;

  // 每一句旁白在對應章節建立便利貼卡片，相機自動運鏡跟隨鋼筆書寫
  story.lines.forEach((L) => {
    if (!api.isEnd(L.i)) api.placeholder(L.i);
  });

  return {
    render(t) {},
  };
};
