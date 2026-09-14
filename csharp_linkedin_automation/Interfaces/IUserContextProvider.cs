public interface IUserContextProvider
{
    int GetYearsOfExperience(string areaOfExpertise);
    string GetLastWorkingDay();
    0987void InjectCookies(string url, string cookies);DateTime GetDateOfJoining();
}