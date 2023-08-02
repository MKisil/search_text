import json
import os
import re
import pymorphy2
import jinja2
from fuzzywuzzy import fuzz

morph = pymorphy2.MorphAnalyzer(lang='uk')


def search_keywords(k_words, text):
    dct_kwords_count = {}
    for kw in k_words:
        normal_form_kw = morph.parse(kw)[0].normal_form
        dct_kwords_count[kw] = 0
        for w in text:
            if fuzz.ratio(kw, w) > 65:
                normal_form_w = morph.parse(w)[0].normal_form
                if bool(re.match(rf'{kw}?[а-яіїєґ]{{,3}}', w)) or bool(re.match(rf'{w}[а-яіїєґ]{{,3}}\b', kw)):
                    dct_kwords_count[kw] += 1
                    delete_word_from_text(w, text)
                elif ('не' in w[:2] or 'не' in kw[:2]) and not ('не' in w[:2] and 'не' in kw[:2]):
                    continue
                elif bool(re.match(rf'{normal_form_kw}?[а-яіїєґ]{{,3}}', normal_form_w)):
                    dct_kwords_count[kw] += 1
                    delete_word_from_text(w, text)
                elif fuzz.ratio(normal_form_kw, normal_form_w) >= 80:
                    dct_kwords_count[kw] += 1
                    delete_word_from_text(w, text)
                elif fuzz.ratio(kw, w) >= 80:
                    dct_kwords_count[kw] += 1
                    delete_word_from_text(w, text)

    return dct_kwords_count


def search_keyphrases(k_phrases, text):
    dct_kwords_count = {}
    for ph in k_phrases:
        updated_text, phrases_cnt = re.subn(rf'\b{ph[:-1]}?[а-яіїєґ]{{,2}}', '', text)
        text = updated_text

        phrase_words = ph.split()
        for i in range(len(text.split())):
            text_slice = " ".join(text.split()[i:i + len(phrase_words)])
            if fuzz.ratio(ph, text_slice) >= 85:
                phrases_cnt += 1

        dct_kwords_count[ph] = phrases_cnt

    return dct_kwords_count


def delete_word_from_text(w, text):
    indx = text.index(w)
    text.remove(w)
    text.insert(indx, '')


def prepare_text(text, symbols_to_delete):
    text = text.lower().strip()
    for symbol in symbols_to_delete:
        text = text.replace(symbol, '')

    return text


def search():
    keywords_files = os.listdir('keywords')
    conversations_files = os.listdir('conversations')

    result = {}
    for conversation_file in conversations_files:
        print(f'Обробка файлу {conversation_file}')
        with open(f'conversations/{conversation_file}', 'r', encoding='utf-8') as file:
            conversation_text = prepare_text(file.read(), '-,.?!;:…_«»*').split()

        text_for_search_phrases = " ".join(conversation_text)
        text_for_search_words = [w for w in conversation_text if len(w) > 2]

        result[conversation_file] = {}
        for keywords_file in keywords_files:
            with open(f'keywords/{keywords_file}', 'r', encoding='utf-8') as file:
                keywords = prepare_text(file.read(), '-,.?!;:…_«»*').split('\n')
                k_words = set([i for i in keywords if ' ' not in i])
                k_phrases = set([i for i in keywords if ' ' in i])

            found_words = search_keywords(k_words, text_for_search_words)
            found_phrases = search_keyphrases(k_phrases, text_for_search_phrases)

            found_words.update(found_phrases)

            result[conversation_file][keywords_file] = found_words

        with open('result.json', 'w', encoding='utf-8') as file:
            json.dump(result, file, indent=2, ensure_ascii=False)

    print('Завершено.')


def generate_html():
    with open('result.json', encoding='utf-8') as file:
        data = json.loads(file.read())

    template = jinja2.Template("""\
        {% for file in data %}
            <h1>{{ file }}</h1>
            <ul>
                {% for keywords_file in data[file] %}
                    <li>
                        <h2>{{ keywords_file }}</h2>  
                        <ul>
                            {% for keyword in data[file][keywords_file] %}
                                <li>{{ keyword }}: {{ data[file][keywords_file][keyword] }}</li>
                            {% endfor %}
                        </ul>
                    </li>
                {% endfor %}
            </ul>
        {% endfor %}
        """)

    html = template.render(data=data)

    with open('result.html', 'w', encoding='utf-8') as file:
        file.write(html)


if __name__ == '__main__':
    search()
    generate_html()






