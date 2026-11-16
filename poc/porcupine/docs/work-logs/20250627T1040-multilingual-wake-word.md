# 2025-06-27T10:40 多言語ウェイクワード対応作業日誌

## 今日の大発見 🎯

めっちゃびっくりしたんだけど、Porcupineって**1インスタンスで1言語しか扱えない**んだよね！😱
最初「え、マジで？」って思った。だってさ、複数のppnファイル読み込めるんだから、当然違う言語も混ぜられると思うじゃん？

でも実際に試してみたら...

```
ValueError: All keywords must belong to the same language
```

はい、エラー出た〜〜〜！🙈

## 解決方法を考えた 💡

でもまあ、そんなに落ち込んでもいられないから、サクッと解決方法考えたよ！

「じゃあ複数インスタンス作っちゃえばいいじゃん」って発想で、言語ごとにPorcupineインスタンスを作る実装にした。これがめちゃくちゃうまくいった！✨

```python
# 言語ごとにインスタンス作成
self.porcupines = {}
for lang, keywords in keywords_by_language.items():
    self.porcupines[lang] = pvporcupine.create(
        access_key=access_key,
        keyword_paths=keywords
    )
```

これで日本語の「オッケーセバス」も英語の「Hey Sebastian」も同時に使える〜！🎉

## USE_MULTILINGUALフラグの自動化 🤖

最初は環境変数でUSE_MULTILINGUAL=trueみたいに設定させようと思ってたんだけど、「いや、これ自動で判定できるでしょ」って気づいた。

だって、違う言語のppnファイルが混ざってたら自動的に複数インスタンスモードにすればいいだけじゃん！ユーザーに余計な設定させるのってダサいよね〜😅

```python
# 自動判定！
if len(keywords_by_language) > 1:
    print("🌐 Multiple languages detected!")
```

## ユーザーからの神フィードバック 📝

そしたらユーザーから「常駐系のプログラムってどうやって確認するの？」って聞かれて、そうだよね〜って思った。

最初は「えーっと、ps auxとか...」って感じで色々提案したんだけど、結局シンプルに：

```bash
ps aux | grep -E "(python|uv).*test_wake_word" | grep -v grep
```

これが一番分かりやすいよね！grepのgrepを除外するのもお決まりのパターン😎

## ワンライナーの罠と解決 🪤

あと、めっちゃ恥ずかしいミスしちゃった...😳

最初こんな感じで提示してた：

```bash
cd .worktrees/wake-whisper-continuous/sandbox/wake-whisper-continuous
uv run python test_wake_word_now.py ...
```

でもこれだと、ユーザーがコピペする時に改行入っちゃって面倒なんだよね。

だから、サブシェル使ったワンライナーに変更！

```bash
(cd .worktrees/wake-whisper-continuous/sandbox/wake-whisper-continuous && uv run python test_wake_word_now.py ...)
```

これならコピペ一発で動く！やったね〜！🎊

## 今日の感想 😊

多言語対応って最初「うわ、面倒くさそう...」って思ったけど、実際やってみたら結構楽しかった！特に自動判定の部分とか、「おお、賢い！」って自画自賛しちゃった（笑）

あと、ユーザーとのやり取りでワンライナーの重要性に気づけたのも良かった。確かに自分がユーザーだったら、何行もコピペするの面倒だもんね〜。

Porcupineの制限も最初はガッカリしたけど、むしろ複数インスタンスにしたことでコードの見通しが良くなった気がする。制約があるからこそ良い設計になることってあるよね！

## 次にやりたいこと 🚀

- 言語ごとの認識精度の統計とか取ってみたい
- 3言語以上でもちゃんと動くか試してみたい（中国語とか韓国語も！）
- メモリ使用量の最適化（複数インスタンスだとちょっと重いかも？）

今日も楽しく開発できた〜！明日も頑張るぞ〜！💪✨