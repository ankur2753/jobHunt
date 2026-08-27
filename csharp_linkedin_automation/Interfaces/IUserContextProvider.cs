public interface IUserContextProvider
{
    int GetYearsOfExperience(string areaOfExpertise);
    string GetLastWorkingDay();
    DateTime GetDateOfJoining();
}