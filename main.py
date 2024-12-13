import streamlit as st
import pandas as pd
import plotly.express as px
import requests

st.title('Анализ температурных данных и мониторинг текущей температуры через OpenWeatherMap API')
st.write('Статистика по историческим данным. Получение температуры в городе в режиме реального времени')
st.header("Анализ исторических данных")
st.subheader('Загрузка данных')


upload_file = st.file_uploader("Загрузите CSV-файл", type=['csv'])

if upload_file is not None:

    df = pd.read_csv(upload_file)
    st.dataframe(df)

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['rolling_mean_temperature'] = df.groupby(['city', 'season'])['temperature'] \
        .transform(lambda x: x.rolling(window=30).mean())
    df['rolling_mean_temperature'] = df['rolling_mean_temperature'].fillna(df['temperature'])
    temp_data = df.groupby(['city', 'season'])['rolling_mean_temperature'].agg(['mean', 'std']).reset_index()
    df = df.merge(temp_data, on=['city', 'season'])

    df['lower_temp'] = df['mean'] - 2 * df['std']
    df['upper_temp'] = df['mean'] + 2 * df['std']
    df['anomaly'] = (df['temperature'] < df['lower_temp']) | \
                    (df['temperature'] > df['upper_temp'])

    unique_cities = df['city'].unique().tolist() # cписок городов, которые есть в файле
    selected_city = st.selectbox('Выберите город:', [''] + unique_cities)

    if selected_city:

        filtered_df = df[df['city'] == selected_city].reset_index(drop=True)

        descriptive_stats = filtered_df['temperature'].describe()
        st.subheader('Описательная статистика')
        st.table(descriptive_stats)

        st.subheader(f'Данные по выбранному городу:')
        st.dataframe(filtered_df)

        # Временной ряд температур по годам и сезонам
        filtered_df['year'] = pd.to_datetime(filtered_df['timestamp']).dt.year

        season_colors = {
            'winter': 'blue',
            'spring': 'green',
            'summer': 'yellow',
            'autumn': 'orange'
        }

        seasons_list = filtered_df['season'].unique()
        years_list = filtered_df['year'].unique()

        st.subheader("Временной ряд температур по сезонам")

        selected_years = st.multiselect("Выберите год:", sorted(years_list), default=2010)

        default_season_index = list(seasons_list).index('spring')
        selected_season = st.selectbox("Выберите сезон:", seasons_list, index=default_season_index)

        season_year_filtered_df = filtered_df[(filtered_df['season'] == selected_season) &
                                                  (filtered_df['year'].isin(selected_years))]

        fig = px.line(season_year_filtered_df, x='timestamp', y='temperature',
                      color='season',
                      color_discrete_map=season_colors,
                      title=f'Температурный ряд для выбранного сезона',
                      hover_data=['season'],
                      labels={'temperature': 'Температура', 'timestamp': 'Дата'})

        # Аномалии
        anomalies = season_year_filtered_df[season_year_filtered_df['anomaly']]
        fig.add_scatter(x=anomalies['timestamp'], y=anomalies['temperature'], mode='markers',
                            marker=dict(color='red', size=3), name='Аномалии', hovertext=anomalies['season'])

        fig.update_layout(
            yaxis_title='Температура',
            xaxis_title='Дата',
            title=dict(x=0.5)
        )

        # Ползунок для сужения временного ряда, если выбрано два и более года
        if len(selected_years) > 1:
            fig.update_layout(xaxis=dict(rangeslider=dict(visible=True), type='date'))
            st.write("Перемещайте ползунок, чтобы сузить временной ряд")

        st.plotly_chart(fig, use_container_width=True)

        # Сезонный профиль выбранного города
        st.subheader("Сезонные профили температуры")
        st.write(selected_city)

        seasonal_stats = filtered_df.groupby(['city', 'season']).agg({'temperature': ['mean', 'std']}).reset_index()
        seasonal_stats.columns = ['city', 'season', 'mean_temperature', 'std_temperature']

        seasonal_stats['temperature'] = seasonal_stats.apply(
            lambda row: f"{row['mean_temperature']:.2f} ± {row['std_temperature']:.2f}",
            axis=1
        )
        result_table = seasonal_stats[['season', 'temperature']]
        st.table(result_table)
    else:
        st.write('Пожалуйста, выберите город для продолжения')


    st.header("OpenWeatherMap")
    st.write('С помощью API-ключа вы сможете узнать температуру в городе в настоящие момент,'
             ' и опередить считается ли она нормальной для выбранного сезона')


    # Функция для получения температуры по API
    def get_temp_api(name_sity, api_key):
        url_name = "http://api.openweathermap.org/data/2.5/weather?"
        url = url_name + "q=" + name_sity + "&appid=" + api_key + "&units=metric"
        response = requests.get(url)

        if response.status_code == 200:
            data_res = response.json()
            current_temperature = data_res["main"]["temp"]
            return current_temperature, None
        else:
            return None, response.json().get("message", "Unknown error")


    # Проверка на аномальность
    def chek_abnormal_temp(df, name_city, season, temp_api):
        temp_limits = df[(df['city'] == name_city) & (df['season'] == season)][['lower_temp', 'upper_temp']]
        first_row = temp_limits.iloc[0]
        l_temp = first_row['lower_temp']
        upp_temp = first_row['upper_temp']

        if l_temp < temp_api < upp_temp:
            return f'Normal temperature for {name_city} in {season}'
        else:
            return f'Abnormal temperatures for {name_city} in {season}'

    st.subheader("Проверка температуры по API")
    api_key = st.text_input("Введите ваш API-ключ OpenWeatherMap:", type="password")

    if api_key:
        city = st.text_input("Введите название города:")
        if city:
            temperature, error_message = get_temp_api(city, api_key)

            if error_message:
                st.error(f"Ошибка: {error_message}")
            else:
                st.success(f"Current temperature in {city}: {temperature}°C")

            st.subheader('Проверка температуры на аномальность для выбранного сезона')

            unique_seasons = df['season'].unique().tolist()
            season = st.selectbox("Выберите сезон:", [''] + unique_seasons)

            if season:
                if city in df['city'].unique():
                    st.success(chek_abnormal_temp(df, city, season, temperature))
                else:
                    st.warning("К сожалению, для данного города невозможно определить аномальность")
            else:
                st.write("Пожалуйста, выберите сезон")

    else:
        st.warning("Пожалуйста, введите ваш API-ключ для получения данных о погоде.")
else:
    st.write("Пожалуйста, загрузите файл")