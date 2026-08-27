public interface ICookieInjector
{
    string ReadCookiesFromFile(string filePath);
    void InjectCookies(string cookies);
}